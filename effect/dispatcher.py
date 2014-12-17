"""
Dispatcher!
"""

from characteristic import attributes


class NoEffectHandlerError(Exception):
    """The dispatcher can't handle the given intent."""


@attributes(['mapping'], apply_with_init=False)
class TypeDispatcher(object):
    """
    An Effect dispatcher which looks up the performer to use by type.
    """
    def __init__(self, mapping):
        """
        :param collections.Mapping mapping: A mapping of intent type to
        functions taking an intent and a box which perform the intent.
        """
        self.mapping = mapping

    def __call__(self, intent, box):
        t = type(intent)
        if t not in self.mapping:
            raise NoEffectHandlerError("No handler for %s found in %s"
                                       % (intent, self))
        return self.mapping[type(intent)](intent, box)


@attributes(['dispatchers'], apply_with_init=False)
class ComposedDispatcher(object):
    """
    A dispatcher which composes other dispatchers.

    The dispatchers given will be passed the intent in order. If any
    dispatcher raises NoEffectHandlerError, the next one will be tried.
    """
    def __init__(self, dispatchers):
        """
        :param collections.Iterable dispatchers: Dispatchers to try.
        """
        self.dispatchers = dispatchers

    def __call__(self, intent, box):
        for dispatcher in self.dispatchers:
            try:
                return dispatcher(intent, box)
            except NoEffectHandlerError:
                pass
        else:
            raise NoEffectHandlerError("No handler for %r found in any of %r"
                                       % (intent, self.dispatchers))
