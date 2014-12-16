"""
Dispatcher!
"""

class Dispatcher(object):
    """
    An Effect dispatcher which looks up the performer to use by type.
    """
    def __init__(self, mapping):
        """
        :param dict mapping: A mapping of intent type to intent performers.
        """
        self.mapping = mapping

    def __call__(self, intent, box):
        return self.mapping[type(intent)](intent, box)

    def merge(self, other_dispatcher):
        """
        Create a new dispatcher based on this one and another,
        preferring the performers in the other.
        """
        mapping = self.mapping.copy()
        mapping.update(other_dispatcher.mapping)
        return Dispatcher(mapping)
