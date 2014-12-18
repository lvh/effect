from __future__ import absolute_import

import sys

from functools import partial

from testtools import TestCase
from testtools.matchers import MatchesListwise, Equals, MatchesException

from twisted.trial.unittest import SynchronousTestCase
from twisted.internet.defer import succeed, fail
from twisted.internet.task import Clock

from . import Effect, parallel, ConstantIntent, Delay, ErrorIntent, base_dispatcher
from . import perform as base_perform
from .dispatcher import ComposedDispatcher
from .twisted import (
    deferred_performer,
    exc_info_to_failure,
    make_twisted_dispatcher,
    perform)


class ParallelTests(SynchronousTestCase):
    """Tests for :func:`parallel`."""
    def test_parallel(self):
        """
        'parallel' results in a list of results of the given effects, in the
        same order that they were passed to parallel.
        """
        d = perform(
            ComposedDispatcher([make_twisted_dispatcher(None), base_dispatcher]),
            parallel([Effect(ConstantIntent('a')),
                      Effect(ConstantIntent('b'))]))
        self.assertEqual(self.successResultOf(d), ['a', 'b'])


class DelayTests(SynchronousTestCase):
    """Tess for :class:`Delay`."""
    def test_delay(self):
        """
        Delay intents will cause time to pass with reactor.callLater, and
        result in None.
        """
        clock = Clock()
        called = []
        eff = Effect(Delay(1)).on(called.append)
        d = perform(make_twisted_dispatcher(clock), eff)
        self.assertEqual(called, [])
        clock.advance(1)
        self.assertEqual(self.successResultOf(d), None)
        self.assertEqual(called, [None])


class TwistedPerformTests(SynchronousTestCase, TestCase):

    skip = None  # Horrible hack to make testtools play with trial...

    def setUp(self):
        self.dispatcher = ComposedDispatcher([make_twisted_dispatcher(None),
                                              base_dispatcher])

    def test_perform(self):
        """
        effect.twisted.perform returns a Deferred which fires with the ultimate
        result of the Effect.
        """
        e = Effect(ConstantIntent("foo"))
        d = perform(self.dispatcher, e)
        self.assertEqual(self.successResultOf(d), 'foo')

    def test_perform_failure(self):
        """
        effect.twisted.perform fails the Deferred it returns if the ultimate
        result of the Effect is an exception.
        """
        e = Effect(ErrorIntent(ValueError('oh dear')))
        d = perform(self.dispatcher, e)
        f = self.failureResultOf(d)
        self.assertEqual(f.type, ValueError)
        self.assertEqual(str(f.value), 'oh dear')

    def test_deferred_performer(self):
        """
        TODO: @deferred_performer
        """
        deferred = succeed('foo')
        e = Effect('meaningless').on(success=lambda x: ('success', x))
        dispatcher = lambda i: lambda d, box: deferred_performer(lambda dispatcher, intent: deferred)(d, i, box)
        result = perform(dispatcher, e)
        self.assertEqual(self.successResultOf(result),
                         ('success', 'foo'))

    def test_deferred_performer_failure(self):
        """
        A failing Deferred returned from a @deferred_performer causes error
        handlers to be called with an exception tuple based on the failure.
        """
        deferred = fail(ValueError('foo'))
        e = Effect('meaningless').on(error=lambda e: ('error', e))
        dispatcher = lambda i: lambda d, box: deferred_performer(lambda dispatcher, intent: deferred)(d, i, box)
        result = self.successResultOf(perform(dispatcher, e))
        self.assertThat(
            result,
            MatchesListwise([
                Equals('error'),
                MatchesException(ValueError('foo'))]))
        # The traceback element is None, because we constructed the failure
        # without a traceback.
        self.assertIs(result[1][2], None)


class ExcInfoToFailureTests(TestCase):
    """Tests for :func:`exc_info_to_failure`."""

    def test_exc_info_to_failure(self):
        """
        :func:`exc_info_to_failure` converts an exc_info tuple to a
        :obj:`Failure`.
        """
        try:
            raise RuntimeError("foo")
        except:
            exc_info = sys.exc_info()

        failure = exc_info_to_failure(exc_info)
        self.assertIs(failure.type, RuntimeError)
        self.assertEqual(str(failure.value), "foo")
        self.assertIs(failure.tb, exc_info[2])
