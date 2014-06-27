from __future__ import print_function
from . import thread

PRINT_LOCK = thread.Lock()


def show(*args, **kw):
    with PRINT_LOCK:
        print(*args, **kw)


class DictObj(dict):
    """ Dictionary with attribute syntax to get, set and delete items.
    """
    def __getattr__(self, item):
        try:
            return self[item]
        except KeyError:
            raise AttributeError(item)

    def __setattr__(self, key, value):
        self[key] = value

    def __delattr__(self, item):
        try:
            del self[item]
        except KeyError:
            raise AttributeError(item)