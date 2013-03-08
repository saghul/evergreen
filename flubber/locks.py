#
# This file is part of flubber. See the NOTICE for more information.
#

import flubber

from flubber.timeout import Timeout

__all__ = ['Semaphore', 'BoundedSemaphore', 'RLock', 'Condition']


class Semaphore(object):

    def __init__(self, value=1):
        if value < 0:
            raise ValueError("Semaphore must be initialized with a positive number, got %s" % value)
        self._counter = value
        self._waiters = set()

    def __repr__(self):
        params = (self.__class__.__name__, hex(id(self)),
                  self._counter, len(self._waiters))
        return '<%s at %s c=%s _w[%s]>' % params

    __str__ = __repr__

    def acquire(self, blocking=True, timeout=None):
        if self._counter > 0:
            self._counter -= 1
            return True
        elif not blocking:
            return False
        else:
            current = flubber.current.task
            self._waiters.add(current)
            timer = Timeout(timeout)
            timer.start()
            loop = flubber.current.loop
            try:
                while self._counter <= 0:
                    loop.switch()
            except Timeout, e:
                if e is timer:
                    return False
                raise
            else:
                self._counter -= 1
                return True
            finally:
                timer.cancel()
                self._waiters.discard(current)

    def release(self):
        self._counter += 1
        if self._waiters:
            flubber.current.loop.call_soon(self._notify_waiters)

    def _notify_waiters(self):
        if self._waiters and self._counter > 0:
            waiter = self._waiters.pop()
            waiter.switch()

    def __enter__(self):
        self.acquire()

    def __exit__(self, typ, val, tb):
        self.release()


class BoundedSemaphore(Semaphore):

    def __init__(self, value=1):
        super(BoundedSemaphore, self).__init__(value)
        self._initial_counter = value

    def release(self):
        if self._counter >= self._initial_counter:
            raise ValueError, "Semaphore released too many times"
        return super(BoundedSemaphore, self).release()


class RLock(object):

    def __init__(self):
        self._block = Semaphore()
        self._count = 0
        self._owner = None

    def acquire(self, blocking=True, timeout=None):
        me = flubber.current.task
        if self._owner is me:
            self._count += 1
            return True
        r = self._block.acquire(blocking, timeout)
        if r:
            self._owner = me
            self._count = 1
        return r

    def release(self):
        if self._owner is not flubber.current.task:
            raise RuntimeError('cannot release un-aquired lock')
        self._count = count = self._count - 1
        if not count:
            self._owner = None
            self._block.release()

    def __enter__(self):
        return self.acquire()

    def __exit__(self, typ, value, tb):
        self.release()

    # Needed by condition

    def _acquire_restore(self, state):
        self._block.acquire()
        self._count, self._owner = state

    def _release_save(self):
        state = (self._count, self._owner)
        self._count = 0
        self._owner = None
        self._block.release()
        return state

    def _is_owned(self):
        return self._owner is flubber.current.task


class Condition(object):

    def __init__(self, lock=None):
        if lock is None:
            lock = RLock()
        self._lock = lock
        self._waiters = []

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

    def wait(self, timeout=None):
        if not self._is_owned():
            raise RuntimeError('cannot wait on un-acquired lock')
        waiter = Semaphore()
        waiter.acquire()
        self._waiters.append(waiter)
        saved_state = self._release_save()
        try:
            return waiter.acquire(timeout=timeout)
        finally:
            self._acquire_restore(saved_state)

    def notify(self, n=1):
        if not self._is_owned():
            raise RuntimeError('cannot wait on un-acquired lock')
        __waiters = self._waiters
        waiters = __waiters[:n]
        if not waiters:
            return
        for waiter in waiters:
            waiter.release()
            try:
                __waiters.remove(waiter)
            except ValueError:
                pass

    def notify_all(self):
        self.notify(len(self._waiters))

    def _acquire_restore(self, state):
        self._lock.acquire()

    def _release_save(self):
        self._lock.release()

    def _is_owned(self):
        # Return True if lock is owned by current_thread.
        # This method is called only if __lock doesn't have _is_owned().
        if self._lock.acquire(False):
            self._lock.release()
            return False
        else:
            return True

    def __enter__(self):
        return self._lock.__enter__()

    def __exit__(self, *args):
        return self._lock.__exit__(*args)

