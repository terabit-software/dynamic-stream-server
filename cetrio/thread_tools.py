import threading


def Condition(lock=None):
    """ Return a Condition object using a `Lock` instead of a `RLock`
        by default.
    """
    if lock is None:
        lock = threading.Lock()
    return threading.Condition(lock)
