from __future__ import print_function
import sys
from . import thread

PRINT_LOCK = thread.Lock()


def show(*args, **kw):
    """ Print message with lock.
    """
    with PRINT_LOCK:
        print(*args, **kw)
        sys.stdout.flush()


def show_close(fn, msg, top_line_break=False, ok_msg='[ok]', err_msg='[fail]'):
    """ Call a function (usually to close a part of the program) and show
        a message.
    """
    if top_line_break:
        show()
    show(msg, end=' ')
    try:
        fn()
    except:
        show(err_msg)
        raise
    show(ok_msg)


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