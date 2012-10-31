
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

    def __enter__(self):
        self.acquire()

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

    def __exit__(self, typ, val, tb):
        self.release()


#TODO: check these other clasess below

class BoundedSemaphore(Semaphore):
    """A bounded semaphore checks to make sure its current value doesn't exceed
    its initial value. If it does, ValueError is raised. In most situations
    semaphores are used to guard resources with limited capacity. If the
    semaphore is released too many times it's a sign of a bug. If not given,
    *value* defaults to 1."""
    def __init__(self, value=1):
        super(BoundedSemaphore, self).__init__(value)
        self.original_counter = value

    def release(self, blocking=True):
        """Release a semaphore, incrementing the internal counter by one. If
        the counter would exceed the initial value, raises ValueError.  When
        it was zero on entry and another thread is waiting for it to become
        larger than zero again, wake up that thread.

        The *blocking* argument is for consistency with :class:`CappedSemaphore`
        and is ignored"""
        if self.counter >= self.original_counter:
            raise ValueError, "Semaphore released too many times"
        return super(BoundedSemaphore, self).release(blocking)

class CappedSemaphore(object):
    """A blockingly bounded semaphore.

    Optionally initialize with a resource *count*, then :meth:`acquire` and
    :meth:`release` resources as needed. Attempting to :meth:`acquire` when
    *count* is zero suspends the calling greenthread until count becomes nonzero
    again.  Attempting to :meth:`release` after *count* has reached *limit*
    suspends the calling greenthread until *count* becomes less than *limit*
    again.

    This has the same API as :class:`threading.Semaphore`, though its
    semantics and behavior differ subtly due to the upper limit on calls
    to :meth:`release`.  It is **not** compatible with
    :class:`threading.BoundedSemaphore` because it blocks when reaching *limit*
    instead of raising a ValueError.

    It is a context manager, and thus can be used in a with block::

      sem = CappedSemaphore(2)
      with sem:
        do_some_stuff()
    """
    def __init__(self, count, limit):
        if count < 0:
            raise ValueError("CappedSemaphore must be initialized with a "
                             "positive number, got %s" % count)
        if count > limit:
            # accidentally, this also catches the case when limit is None
            raise ValueError("'count' cannot be more than 'limit'")
        self.lower_bound = Semaphore(count)
        self.upper_bound = Semaphore(limit-count)

    def __repr__(self):
        params = (self.__class__.__name__, hex(id(self)),
                  self.balance, self.lower_bound, self.upper_bound)
        return '<%s at %s b=%s l=%s u=%s>' % params

    def __str__(self):
        params = (self.__class__.__name__, self.balance,
                  self.lower_bound, self.upper_bound)
        return '<%s b=%s l=%s u=%s>' % params

    def locked(self):
        """Returns true if a call to acquire would block."""
        return self.lower_bound.locked()

    def bounded(self):
        """Returns true if a call to release would block."""
        return self.upper_bound.locked()

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
        if not blocking and self.locked():
            return False
        self.upper_bound.release()
        try:
            return self.lower_bound.acquire()
        except:
            self.upper_bound.counter -= 1
            # using counter directly means that it can be less than zero.
            # however I certainly don't need to wait here and I don't seem to have
            # a need to care about such inconsistency
            raise

    def __enter__(self):
        self.acquire()

    def release(self, blocking=True):
        """Release a semaphore.  In this class, this behaves very much like
        an :meth:`acquire` but in the opposite direction.

        Imagine the docs of :meth:`acquire` here, but with every direction
        reversed.  When calling this method, it will block if the internal
        counter is greater than or equal to *limit*."""
        if not blocking and self.bounded():
            return False
        self.lower_bound.release()
        try:
            return self.upper_bound.acquire()
        except:
            self.lower_bound.counter -= 1
            raise

    def __exit__(self, typ, val, tb):
        self.release()

    @property
    def balance(self):
        """An integer value that represents how many new calls to
        :meth:`acquire` or :meth:`release` would be needed to get the counter to
        0.  If it is positive, then its value is the number of acquires that can
        happen before the next acquire would block.  If it is negative, it is
        the negative of the number of releases that would be required in order
        to make the counter 0 again (one more release would push the counter to
        1 and unblock acquirers).  It takes into account how many greenthreads
        are currently blocking in :meth:`acquire` and :meth:`release`."""
        return self.lower_bound.balance - self.upper_bound.balance
