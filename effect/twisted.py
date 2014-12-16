"""
Twisted integration for the Effect library.

This is largely concerned with bridging the gap between Effects and Deferreds.

Note that the core effect library does *not* depend on Twisted, but this module
does.

The main useful thing you should be concerned with is the :func:`perform`
function, which is like effect.perform except that it returns a Deferred with
the final result, and also sets up Twisted/Deferred specific effect handling
by using its default effect dispatcher, twisted_dispatcher.
"""

from __future__ import absolute_import

from functools import partial

import sys

from twisted.internet.defer import Deferred, maybeDeferred, gatherResults
from twisted.python.failure import Failure
from twisted.internet.task import deferLater

from . import dispatch_method, perform as base_perform, Delay
from effect import ParallelEffects
from effect.dispatcher import Dispatcher


def deferred_to_box(d, box):
    """
    Make a Deferred pass its success or fail events on to the given box.
    """
    d.addCallbacks(box.succeed, lambda f: box.fail((f.type, f.value, f.tb)))


def deferred_performer(f):
    """A decorator for writing dispatchers that return Deferreds."""
    @wraps(f)
    def inner(intent, box, *args, **kwargs):
        try:
            result = f(*args, **kwargs)
        except:
            box.fail(sys.exc_info())
        else:
            if isinstance(result, Deferred):
                deferred_to_box(result, box)
            else:
                box.succeed(result)
    return inner


def make_twisted_dispatcher(reactor):
    """
    Return a :obj:`Dispatcher` which supports some standard intents
    using Twisted mechanisms.

      - :obj:`ParallelIntent` with Twisted's :func:`gatherResults`
      - :obj:`Delay` with Twisted's ``IReactorTime.callLater``
    """
    return make_dispatcher({
        ParallelEffects: lambda i, b: perform_parallel(i, reactor),
        Delay: lambda i, b: perform_delay(i, reactor),
        })


@deferred_performer
def perform_parallel(parallel, reactor):
    """
    Perform a ParallelEffects intent by using the Deferred gatherResults
    function.
    """
    return gatherResults(
        [maybeDeferred(perform, reactor, e, dispatcher=twisted_dispatcher)
         for e in parallel.effects])


def perform(reactor, effect, dispatcher):
    """
    Perform an effect, handling Deferred results and returning a Deferred
    that will fire with the effect's ultimate result.
    """
    d = Deferred()
    eff = effect.on(
        success=d.callback,
        error=lambda e: d.errback(exc_info_to_failure(e)))
    base_perform(eff, dispatcher=partial(dispatcher, reactor))
    return d


@deferred_performer
def perform_delay(delay, reactor):
    return deferLater(reactor, delay.delay, lambda: None)


def exc_info_to_failure(exc_info):
    """Convert an exc_info tuple to a :class:`Failure`."""
    return Failure(exc_info[1], exc_info[0], exc_info[2])
