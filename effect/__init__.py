"""
A system for helping you separate your IO and state-manipulation code
(hereafter referred to as "effects") from everything else, thus allowing
the majority of your code to be trivially testable and composable (that is,
have the general benefits of purely functional code).

TODO: an effect implementation of ParallelEffects that uses threads?
TODO: an effect implementation of ParallelEffects that is actually serial,
      as a fallback?
TODO: integration with other asynchronous libraries like asyncio, trollius,
      eventlet
"""

from __future__ import print_function

from functools import partial
import sys

from characteristic import attributes

import six

from .continuation import trampoline
from .dispatcher import TypeDispatcher


@attributes(['intent', 'callbacks'], apply_with_init=False)
class Effect(object):
    """
    Wrap an object that describes how to perform some effect (called an
    "intent"), and allow attaching callbacks to be run when the effect
    is complete.

    (You're an object-oriented programmer.
     You probably want to subclass this.
     Don't.)
    """
    def __init__(self, intent, callbacks=None):
        """
        :param intent: An object that describes an effect to be
            performed.
        """
        self.intent = intent
        if callbacks is None:
            callbacks = []
        self.callbacks = callbacks

    def on(self, success=None, error=None):
        """
        Return a new Effect that will invoke either the success or error
        callbacks provided based on whether this Effect completes sucessfully
        or in error.
        """
        return Effect(self.intent,
                      callbacks=self.callbacks + [(success, error)])


class _Box(object):
    """
    An object into which an effect dispatcher can place a result.
    """
    def __init__(self, cont):
        self._cont = cont

    def succeed(self, result):
        """
        Indicate that the effect has succeeded, and the result is available.
        """
        self._cont((False, result))

    def fail(self, result):
        """
        Indicate that the effect has failed. result must be an exc_info tuple.
        """
        self._cont((True, result))


def perform(dispatcher, effect, recurse_effects=True):
    """
    Perform an effect by invoking the dispatcher, and invoke callbacks
    associated with it.

    The dispatcher will be passed a "box" argument and the intent. The box
    is an object that lets the dispatcher specify the result (optionally
    asynchronously). See :func:`_Box.succeed` and :func:`_Box.fail`.

    Note that this function does _not_ return the final result of the effect.
    You may instead want to use :func:`sync_perform` or
    :func:`effect.twisted.perform`.

    :returns: None
    """

    def _run_callbacks(bouncer, chain, result):
        is_error, value = result
        if recurse_effects and type(value) is Effect:
            bouncer.bounce(
                _perform,
                Effect(value.intent, callbacks=value.callbacks + chain))
            return
        if not chain:
            return
        cb = chain[0][is_error]
        if cb is not None:
            result = guard(cb, value)
        chain = chain[1:]
        bouncer.bounce(_run_callbacks, chain, result)

    def _perform(bouncer, effect):
        dispatcher(
            dispatcher,
            effect.intent,
            _Box(partial(_run_callbacks, bouncer, effect.callbacks)))

    trampoline(_perform, effect)


def guard(f, *args, **kwargs):
    """
    Run a function.

    Return (is_error, result), where is_error is a boolean indicating whether
    it raised an exception. In that case result will be sys.exc_info().
    """
    try:
        return (False, f(*args, **kwargs))
    except:
        return (True, sys.exc_info())


@attributes(['effects'], apply_with_init=False)
class ParallelEffects(object):
    """
    An effect intent that asks for a number of effects to be run in parallel,
    and for their results to be gathered up into a sequence.

    There is an implementation of this intent for Twisted, as long as the
    effect.twisted.perform function is used to perform the effect.

    Alternative implementations could run the child effects in threads, or use
    some other concurrency mechanism. Of course, the implementation strategy
    for this effect will need to cooperate with the effects being parallelized
    -- there's not much use running a Deferred-returning effect in a thread.
    """
    def __init__(self, effects):
        self.effects = effects


def parallel(effects):
    """
    Given multiple Effects, return one Effect that represents the aggregate of
    all of their effects.
    The result of the aggregate Effect will be a list of their results, in
    the same order as the input to this function.
    """
    return Effect(ParallelEffects(list(effects)))


@attributes(['delay'], apply_with_init=False)
class Delay(object):
    """
    An effect which represents a delay in time.

    When performed, the specified delay will pass and then the effect will
    result in None.
    """
    def __init__(self, delay):
        self.delay = delay


class NotSynchronousError(Exception):
    """Performing an effect did not immediately return a value."""


def sync_perform(dispatcher, effect, recurse_effects=True):
    """
    Perform an effect, and return its ultimate result. If the final result is
    an error, the exception will be raised. This is useful for testing, and
    also if you're using blocking effect implementations.

    This requires that the effect (and all effects returned from any of its
    callbacks) to be synchronous. If this is not the case, NotSynchronousError
    will be raised.
    """
    successes = []
    errors = []

    def success(x):
        successes.append(x)

    def error(x):
        errors.append(x)

    effect = effect.on(success=success, error=error)
    perform(dispatcher, effect, recurse_effects=recurse_effects)
    if successes:
        return successes[0]
    elif errors:
        six.reraise(*errors[0])
    else:
        raise NotSynchronousError("Performing %r was not synchronous!"
                                  % (effect,))


def sync_performer(f):
    """
    A decorator for performers that return a value synchronously.

    The returned function accepts an intent and a box, and the wrapped
    function will be called with only the intent. The result of the
    function will be provided as the result to the box.
    """
    def inner(dispatcher, intent, box):
        try:
            box.succeed(f(dispatcher, intent))
        except:
            box.fail(sys.exc_info())
    return inner


@attributes(['result'], apply_with_init=False)
class ConstantIntent(object):
    """An intent that returns a pre-specified result when performed."""
    def __init__(self, result):
        self.result = result


@sync_performer
def perform_constant(dispatcher, intent):
    return intent.result


@attributes(['exception'], apply_with_init=False)
class ErrorIntent(object):
    """An intent that raises a pre-specified exception when performed."""
    def __init__(self, exception):
        self.exception = exception


@sync_performer
def perform_error(dispatcher, intent):
    raise intent.exception


@attributes(['func'], apply_with_init=False)
class FuncIntent(object):
    """
    An intent that returns the result of the specified function.

    Note that FuncIntent is something of a cop-out. It doesn't follow the
    convention of an intent being transparent data that is easy to introspect,
    since it just wraps an opaque callable. This has two drawbacks:

    - it's harder to test, since the only thing you can do is call the
      function, instead of inspect its data.
    - it doesn't offer any ability for changing the way the effect is
      performed.

    If you use FuncIntent in your application code, know that you are giving
    up some ease of testing and flexibility. It's preferable to represent your
    intents as inert objects with public attributes of simple data. However,
    this is useful for integrating wih "legacy" side-effecting code in a quick
    way.
    """
    def __init__(self, func):
        self.func = func


@sync_performer
def perform_func(dispatcher, intent):
    return intent.func()


base_dispatcher = TypeDispatcher({
    ConstantIntent: perform_constant,
    ErrorIntent: perform_error,
    FuncIntent: perform_func,
})
