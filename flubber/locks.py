# -*- coding: utf-8 -
#
# This file is part of flubber. See the NOTICE for more information.

import flubber

from flubber.timeout import Timeout

__all__ = ['Semaphore', 'BoundedSemaphore', 'RLock', 'Condition']


class Semaphore(object):
    """An unbounded semaphore.
    Optionally initialize with a resource *count*, then :meth:`acquire` and
    :meth:`release` resources as needed. Attempting to :meth:`acquire` when
    *count* is zero suspends the calling task until *count* becomes
    nonzero again.

    This is API-compatible with :class:`threading.Semaphore`.

    It is a context manager, and thus can be used in a with block::

      sem = Semaphore(2)
      with sem:
        do_some_stuff()

    If not specified, *value* defaults to 1.
    """

    def __init__(self, value=1):
        if value < 0:
            raise ValueError("Semaphore must be initialized with a positive number, got %s" % value)
        self.__counter = value
        self.__waiters = set()

    def __repr__(self):
        params = (self.__class__.__name__, hex(id(self)),
                  self.__counter, len(self.__waiters))
        return '<%s at %s c=%s _w[%s]>' % params

    __str__ = __repr__

    def acquire(self, blocking=True, timeout=None):
        """Acquire a semaphore.

        When invoked without arguments: if the internal counter is larger than
        zero on entry, decrement it by one and return immediately. If it is zero
        on entry, block, waiting until some other thread has called release() to
        make it larger than zero. This is done with proper interlocking so that
        if multiple acquire() calls are blocked, release() will wake exactly one
        of them up. The implementation may pick one at random, so the order in
        which blocked threads are awakened should not be relied on. There is no
        return value in this case.

        When invoked with blocking set to true, do the same thing as when called
        without arguments, and return true.

        When invoked with blocking set to false, do not block. If a call without
        an argument would block, return false immediately; otherwise, do the
        same thing as when called without arguments, and return true."""
        if self.__counter > 0:
            self.__counter -= 1
            return True
        elif not blocking:
            return False
        else:
            current = flubber.current.task
            self.__waiters.add(current)
            timer = Timeout(timeout)
            timer.start()
            loop = flubber.current.loop
            try:
                while self.__counter <= 0:
                    loop.switch()
            except Timeout, e:
                if e is timer:
                    return False
                raise
            else:
                self.__counter -= 1
                return True
            finally:
                timer.cancel()
                self.__waiters.discard(current)

    def release(self):
        """Release a semaphore, incrementing the internal counter by one. When
        it was zero on entry and another thread is waiting for it to become
        larger than zero again, wake up that thread.
        ignored"""
        self.__counter += 1
        if self.__waiters:
            flubber.current.loop.call_soon(self._notify_waiters)

    def _notify_waiters(self):
        if self.__waiters and self.__counter > 0:
            waiter = self.__waiters.pop()
            waiter.switch()

    def __enter__(self):
        self.acquire()

    def __exit__(self, typ, val, tb):
        self.release()


class BoundedSemaphore(Semaphore):
    """A bounded semaphore checks to make sure its current value doesn't exceed
    its initial value. If it does, ValueError is raised. In most situations
    semaphores are used to guard resources with limited capacity. If the
    semaphore is released too many times it's a sign of a bug. If not given,
    *value* defaults to 1."""
    def __init__(self, value=1):
        super(BoundedSemaphore, self).__init__(value)
        self.__initial_counter = value

    def release(self, blocking=True):
        """Release a semaphore, incrementing the internal counter by one. If
        the counter would exceed the initial value, raises ValueError.  When
        it was zero on entry and another thread is waiting for it to become
        larger than zero again, wake up that thread."""
        if self.__counter >= self.__initial_counter:
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

