"""
Dispatcher!
"""

from characteristic import attributes


@attributes(['mapping'], apply_with_init=False)
class TypeDispatcher(object):
    """
    An Effect dispatcher which looks up the performer to use by type.
    """
    def __init__(self, mapping):
        """
        :param collections.Mapping mapping: A mapping of intent type to
        functions taking a dispatcher, intent, and a box.
        """
        self.mapping = mapping

    def __call__(self, intent):
        t = type(intent)
        if type(intent) in self.mapping:
            performer = self.mapping[type(intent)]
            return lambda d, box: performer(d, intent, box)


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

    def __call__(self, intent):
        for dispatcher in self.dispatchers:
            performer = dispatcher(intent)
            if performer is not None:
                return performer
