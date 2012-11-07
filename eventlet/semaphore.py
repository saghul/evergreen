
import eventlet


class Semaphore(object):
    """An unbounded semaphore.
    Optionally initialize with a resource *count*, then :meth:`acquire` and
    :meth:`release` resources as needed. Attempting to :meth:`acquire` when
    *count* is zero suspends the calling greenthread until *count* becomes
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

    def acquire(self, blocking=True):
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
        if not blocking and self.__counter <= 0:
            return False
        current = eventlet.core.current_greenlet
        if self.__counter <= 0:
            self.__waiters.add(current)
            try:
                while self.__counter <= 0:
                    eventlet.suspend(switch_back=False)
            finally:
                self.__waiters.discard(current)
        self.__counter -= 1
        return True

    def release(self):
        """Release a semaphore, incrementing the internal counter by one. When
        it was zero on entry and another thread is waiting for it to become
        larger than zero again, wake up that thread.
        ignored"""
        self.__counter += 1
        if self.__waiters:
            hub = eventlet.core.hub
            hub.next_tick(self._notify_waiters)

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

