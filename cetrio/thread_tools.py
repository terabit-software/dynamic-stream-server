import threading
from time import time
from collections import deque
from itertools import islice


Lock = threading.Lock
RLock = threading.Lock


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
        if self._lock.acquire(0):
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
            raise RuntimeError("cannot wait on un-acquired lock")

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
            raise RuntimeError("cannot notify on un-acquired lock")
        all_waiters = self._waiters
        waiters_to_notify = deque(islice(all_waiters, n))
        if not waiters_to_notify:
            return
        for waiter in waiters_to_notify:
            try:
                waiter.release()
            except RuntimeError:
                pass # This waiter might have been released by another condition
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
            raise RuntimeError('Not able stop thread!')
        self._stop_fn()
