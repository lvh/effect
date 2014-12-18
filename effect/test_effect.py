from __future__ import print_function, absolute_import

from testtools import TestCase
from testtools.matchers import (MatchesListwise, Is, Equals, MatchesException,
                                raises)

from . import (Effect, perform,
               base_dispatcher, sync_perform, NotSynchronousError,
               ConstantIntent, ErrorIntent,
               NoPerformerFoundError)


class POPOIntent(object):
    """An example effect intent."""


class SyncPerformEffectTests(TestCase):
    """Tests for :func:`perform_effect`."""

    def test_sync_perform_effect_function_dispatch(self):
        """
        sync_perform returns the result of the effect.
        """
        dispatcher = lambda i: lambda d, box: box.succeed('foo')
        intent = POPOIntent()
        self.assertEqual(
            sync_perform(dispatcher, Effect(intent)),
            'foo')

    def test_sync_perform_async_effect(self):
        """If an effect is asynchronous, sync_effect raises an error."""
        self.assertRaises(
            NotSynchronousError,
            lambda: sync_perform(lambda i: lambda d, box: None,
                                 Effect(ConstantIntent("foo"))))

    def test_error_bubbles_up(self):
        """
        When effect performance fails, the exception is raised up through
        sync_perform.
        """
        self.assertThat(
            lambda: sync_perform(base_dispatcher, Effect(ErrorIntent(ValueError('oh dear')))),
            raises(ValueError('oh dear')))


class EffectPerformTests(TestCase):
    """Tests for perform."""

    def test_no_performer(self):
        """
        When a dispatcher returns None, :class:`NoPerformerFoundError` is raised.
        """
        dispatcher = lambda i: None
        self.assertRaises(
            NoPerformerFoundError,
            perform, dispatcher, Effect(object()))

    def test_success_with_callback(self):
        """
        perform
        - invokes the given dispatcher with the intent and a box
        - uses the result given to the box as the argument of an
          effect's callback
        """
        calls = []
        dispatcher = lambda i: lambda d, box: box.succeed((i, 'dispatched'))
        intent = POPOIntent()
        perform(dispatcher, Effect(intent).on(calls.append))
        self.assertEqual(calls, [(intent, 'dispatched')])

    def test_effects_returning_effects(self):
        """
        When the effect dispatcher returns another effect,
        - that effect is immediately performed with the same dispatcher,
        - the result of that is returned.
        """
        self.assertEqual(
            sync_perform(
                base_dispatcher,
                Effect(ConstantIntent(Effect(ConstantIntent("foo"))))),
            "foo")

    def test_effects_returning_effects_returning_effects(self):
        """
        If an effect returns an effect which immediately returns an effect
        with no callbacks in between, the result of the innermost effect is
        returned from the outermost effect's perform.
        """
        self.assertEqual(
            sync_perform(
                base_dispatcher,
                Effect(
                    ConstantIntent(
                        Effect(
                            ConstantIntent(
                                Effect(
                                    ConstantIntent("foo"))))))),
            "foo")


class CallbackTests(TestCase):
    """Tests for callbacks."""

    def test_success(self):
        """
        An Effect with callbacks
        - performs the wrapped intent,
        - passes the result of that to the callback,
        - returns the result of the callback.
        """
        self.assertEqual(
            sync_perform(
                base_dispatcher,
                Effect(ConstantIntent('constant'))
                .on(success=lambda x: (x, "amended!"))),
            ('constant', 'amended!'))

    def test_success_propagates_effect_exception(self):
        """
        An Effect with callbacks propagates exceptions from performing
        the inner effect when there is no errback.
        """
        self.assertThat(
            lambda:
                sync_perform(
                    base_dispatcher,
                    Effect(ErrorIntent(ValueError('oh dear'))).on(success=lambda x: 'nope')),
            raises(ValueError('oh dear')))

    def test_error_success(self):
        """
        An Effect with callbacks
        - performs the wrapped effect, passing the dispatcher,
        - returns the result (assuming there is no exception).

        In other words, the error handler is skipped when there's no error.
        """
        self.assertEqual(
            sync_perform(
                base_dispatcher,
                Effect(ConstantIntent('constant'))
                .on(error=lambda x: (x, "recovered!"))),
            'constant')

    def test_error(self):
        """
        An Effect with callbacks
        - performs the wrapped effect,
        - in the case of an exception, invokes the errback with exc_info,
        - returns the result of the errback.
        """
        self.assertThat(
            sync_perform(
                base_dispatcher,
                Effect(ErrorIntent(ValueError('oh dear')))
                    .on(error=lambda x: ("handled", x))),
            MatchesListwise([
                Equals('handled'),
                MatchesException(ValueError('oh dear'))]))

    def test_error_propagates_callback_exceptions(self):
        """
        An Effect with callbacks does _not_ catch errors from effect
        implementations.
        """
        self.assertThat(
            lambda:
                sync_perform(
                    base_dispatcher,
                    Effect(ErrorIntent(ValueError('oh dear')))
                        .on(error=lambda x: raise_(ValueError('eb error')))),
            raises(ValueError('eb error')))

    def test_nested_effect_exception_passes_to_outer_error_handler(self):
        """
        If an inner effect raises an exception, it bubbles up and the
        exc_info is passed to the outer effect's error handlers.
        """
        self.assertThat(
            sync_perform(
                base_dispatcher,
                Effect(ConstantIntent(Effect(ErrorIntent(ValueError('oh dear')))))
                    .on(error=lambda x: x)),
            MatchesException(ValueError('oh dear')))

    def test_asynchronous_callback_invocation(self):
        """
        When an Effect that is returned by a callback is resolved
        *asynchronously*, the callbacks will run.
        """
        results = []
        boxes = []
        dispatcher = lambda i: lambda d, box: boxes.append(box)
        intent = POPOIntent()
        eff = Effect(intent).on(success=results.append)
        perform(dispatcher, eff)
        boxes[0].succeed('foo')
        self.assertEqual(results, ['foo'])


# TODO: explicit tests for the dispatcher argument to the dispatcher.
# TODO: tests for dispatcher.py (including ensuring that the top-level
#       dispatcher is always passed trhough)
        
def raise_(e):
    raise e
