import sys
from . import thread
from . import log


class Show(object):
    dsslog = 'dss.log'
    print_lock = thread.Lock()

    def __init__(self, owner, filename=dsslog):
        self.logger = log.Log(owner, filename)

    def __call__(self, *args, **kw):
        """ Print message with lock.and log it.
        """
        with self.print_lock:
            print(*args, **kw)
            sys.stdout.flush()

        sep = kw.get('sep', ' ')
        self.logger.log(sep.join(map(str, args)))


# Generic print with log
show = Show(None)


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