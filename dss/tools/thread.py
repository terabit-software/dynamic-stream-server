import sys
import threading
import functools
from time import time, sleep
from collections import deque
from itertools import islice


Lock = threading.Lock
RLock = threading.RLock
Timer = threading.Timer
if not isinstance(Timer, type):
    # Python 2.x compatibility.
    Timer = threading._Timer


class MetaLockedObject(type):
    def __init__(cls, what, bases, dict):
        super(MetaLockedObject, cls).__init__(what, bases, dict)
        for name in dict.get('__locked_properties__', ()):
            cls.lock_property(name)

    def lock_property(cls, name):
        """ Create a property for the named passed with getter and setter
            functions accessing a "_name" variable through the instance lock.
        """
        attribute_name = '_' + name

        def getter(self):
            with self.lock:
                return getattr(self, attribute_name)

        def setter(self, value):
            with self.lock:
                setattr(self, attribute_name, value)

        prop = property(getter, setter)
        setattr(cls, name, prop)


LockedObjectBase = MetaLockedObject('LockedObjectBase', (object,), {})


class LockedObject(LockedObjectBase):
    __locked_properties__ = ()

    def __init__(self, lock=None):
        # RLock object to reduce the possibilities of deadlocking
        self.lock = lock or RLock()


def lock_method(function):
    """ Decorator for methods of `LockedObject` subclasses.
        It acquires and releases the instance lock before and
        after the execution of the function.
    """
    @functools.wraps(function)
    def decorator(self, *args, **kw):
        with self.lock:
            return function(self, *args, **kw)

    return decorator

# Always raise RuntimeError to be compatible with Py3K
# But, capture both exceptions in case of Py2K
ThreadError = RuntimeError
ThreadErrorCapture = (threading.ThreadError, RuntimeError)

if sys.version_info < (3, 2):
    class Lock(object):

        def __init__(self):
            self._lock = threading.Lock()

        def release(self):
            return self._lock.release()

        def __enter__(self):
            return self._lock.__enter__()

        def __exit__(self, exc_type, exc_val, exc_tb):
            return self._lock.__exit__(exc_type, exc_val, exc_tb)

        def __getattr__(self, item):
            return getattr(self._lock, item)

        # Hook for acquire to block with timeout on old Python versions
        def acquire(self, blocking=True, timeout=-1):
            if not blocking and timeout > 0:
                raise ThreadError('Cannot have a timeout when not blocking.')

            if not blocking:
                return self._lock.acquire(False)

            if timeout < 0:
                return self._lock.acquire(True)

            endtime = time() + timeout
            delay = 0.0005  # 500us
            gotit = False
            while True:
                gotit = self._lock.acquire(False)
                if gotit:
                    break
                remaining = endtime - time()
                if remaining <= 0:
                    break
                delay = min(delay * 2, remaining, .05)
                sleep(delay)
            return gotit


class Condition(object):

    def __init__(self, lock=None):
        if lock is None:
            lock = Lock()
        self._lock = lock
        # Export the lock's acquire() and release() methods
        self.acquire = lock.acquire
        self.release = lock.release
        # If the lock defines _release_save() and/or _acquire_restore(),
        # these override the default implementations (which just call
        # release() and acquire() on the lock).  Ditto for _is_owned().
        try:
            self._release_save = lock._release_save
        except AttributeError:
            pass
        try:
            self._acquire_restore = lock._acquire_restore
        except AttributeError:
            pass
        try:
            self._is_owned = lock._is_owned
        except AttributeError:
            pass
        self._waiters = deque()

    @classmethod
    def from_condition(cls, condition):
        return cls(condition._lock)

    def __enter__(self):
        return self._lock.__enter__()

    def __exit__(self, *args):
        return self._lock.__exit__(*args)

    def __repr__(self):
        return "<Condition(%s, %d)>" % (self._lock, len(self._waiters))

    def _release_save(self):
        self._lock.release()           # No state to save

    def _acquire_restore(self, _):
        self._lock.acquire()           # Ignore saved state

    def _is_owned(self):
        # Return True if lock is owned by current_thread.
        # This method is called only if __lock doesn't have _is_owned().
        if self._lock.acquire(False):
            self._lock.release()
            return False
        else:
            return True

    def _remove_waiter(self, waiter):
        try:
            self._waiters.remove(waiter)
        except ValueError:
            pass

    def _wait(self, waiter, timeout):
        """ Wait on a possibly already acquired lock. """
        saved_state = self._release_save()
        try:    # restore state no matter what (e.g., KeyboardInterrupt)
            if timeout is None:
                waiter.acquire()
                gotit = True
            else:
                if timeout > 0:
                    gotit = waiter.acquire(True, timeout)
                else:
                    gotit = waiter.acquire(False)
            return gotit
        finally:
            self._acquire_restore(saved_state)

    @classmethod
    def wait_for_any(cls, conditions, timeout=None):
        """ Wait on a dictionary of conditions with predicates or an
            iterable of conditions.
        """
        if not conditions:
            raise ValueError("at least one condition should be provided")

        some_cond = next(iter(conditions))
        if any(cond._lock is not some_cond._lock for cond in conditions):
            raise ValueError("all the conditions must use the same lock")

        if not some_cond._is_owned():
            raise ThreadError("cannot wait on un-acquired lock")

        try:
            predicates = conditions.values()
        except AttributeError:
            predicates = None

        endtime = None
        waittime = timeout
        result = predicates and any(f() for f in predicates)
        while not result:
            waiter = Lock()
            for cond in conditions:
                cond._waiters.append(waiter)

            if waittime is not None:
                if endtime is None:
                    endtime = time() + waittime
                else:
                    waittime = endtime - time()
                    if waittime <= 0:
                        break

            waiter.acquire()
            # Any condition of the dictionary can be used to wait.
            result = some_cond._wait(waiter, waittime)

            for cond in conditions:
                cond._remove_waiter(waiter)

            if not predicates:
                break
            result = any(f() for f in predicates)

        return result

    def wait(self, timeout=None):
        return self.wait_for_any([self], timeout)

    def wait_for(self, predicate, timeout=None):
        return self.wait_for_any({self: predicate}, timeout)

    def notify(self, n=1):
        if not self._is_owned():
            raise ThreadError("cannot notify on un-acquired lock")
        all_waiters = self._waiters
        waiters_to_notify = deque(islice(all_waiters, n))
        if not waiters_to_notify:
            return
        for waiter in waiters_to_notify:
            try:
                waiter.release()
            except ThreadErrorCapture:
                pass  # This waiter might have been released
                      # by another condition
            self._remove_waiter(waiter)

    def notify_all(self):
        self.notify(len(self._waiters))


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
            raise ThreadError('Not able stop thread!')
        self._stop_fn()


class IntervalTimer(Timer):
    def run(self):
        while True:
            self.finished.wait(self.interval)
            if self.finished.is_set():
                break
            self.function(*self.args, **self.kwargs)
        self.finished.set()