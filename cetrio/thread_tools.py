import threading

Lock = threading.Lock
RLock = threading.Lock


def Condition(lock=None):
    """ Return a Condition object using a `Lock` instead of a `RLock`
        by default.
    """
    if lock is None:
        lock = Lock()
    return threading.Condition(lock)


class Thread(threading.Thread):
    """ Daemon Thread without the `group` argument.
        If there's a mechanism for stopping the target, it can be added
        (no arguments allowed for simplicity).
    """
    def __init__(self, target=None, args=(), kw=None, name=None, daemon=True,
                 stop_fn=None):
        if kw is None:
            kw = {}
        super(Thread, self).__init__(target=target, args=args, kwargs=kw,
                                     name=name)
        self.daemon = daemon
        self._stop_fn = stop_fn

    def start(self):
        super(Thread, self).start()
        return self

    def stop(self):
        if not self._stop_fn:
            raise RuntimeError('Not able stop thread!')
        self._stop_fn()
