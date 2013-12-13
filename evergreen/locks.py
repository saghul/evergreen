#
# This file is part of Evergreen. See the NOTICE for more information.
#

try:
    from time import monotonic as _time
except ImportError:
    from time import time as _time

import evergreen
from evergreen.timeout import Timeout

__all__ = ['Semaphore', 'BoundedSemaphore', 'Lock', 'RLock', 'Condition', 'Barrier']


class Semaphore(object):

    def __init__(self, value=1):
        if value < 0:
            raise ValueError("Semaphore must be initialized with a positive number, got %s" % value)
        self._counter = value
        self._waiters = set()

    def acquire(self, blocking=True, timeout=None):
        if self._counter > 0:
            self._counter -= 1
            return True
        elif not blocking:
            return False
        else:
            current = evergreen.current.task
            self._waiters.add(current)
            timer = Timeout(timeout)
            timer.start()
            loop = evergreen.current.loop
            try:
                while self._counter <= 0:
                    loop.switch()
            except Timeout as e:
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
            evergreen.current.loop.call_soon(self._notify_waiters)

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
            raise ValueError("Semaphore released too many times")
        return super(BoundedSemaphore, self).release()


class Lock(Semaphore):

    def __init__(self):
        super(Lock, self).__init__(value=1)


class RLock(object):

    def __init__(self):
        self._block = Semaphore()
        self._count = 0
        self._owner = None

    def acquire(self, blocking=True, timeout=None):
        me = evergreen.current.task
        if self._owner is me:
            self._count += 1
            return True
        r = self._block.acquire(blocking, timeout)
        if r:
            self._owner = me
            self._count = 1
        return r

    def release(self):
        if self._owner is not evergreen.current.task:
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
        return self._owner is evergreen.current.task


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

    def wait_for(self, predicate, timeout=None):
        endtime = None
        waittime = timeout
        result = predicate()
        while not result:
            if waittime is not None:
                if endtime is None:
                    endtime = _time() + waittime
                else:
                    waittime = endtime - _time()
                    if waittime <= 0:
                        break
            self.wait(waittime)
            result = predicate()
        return result

    def notify(self, n=1):
        if not self._is_owned():
            raise RuntimeError('cannot wait on un-acquired lock')
        _waiters = self._waiters
        waiters = _waiters[:n]
        for waiter in waiters:
            waiter.release()
            try:
                _waiters.remove(waiter)
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


# A barrier class. Inspired in part by the pthread_barrier_* api and
# the CyclicBarrier class from Java. See
# http://sourceware.org/pthreads-win32/manual/pthread_barrier_init.html and
# http://java.sun.com/j2se/1.5.0/docs/api/java/util/concurrent/CyclicBarrier.html
# for information.
#
# We maintain two main states, 'filling' and 'draining' enabling the barrier
# to be cyclic.  Threads are not allowed into it until it has fully drained
# since the previous cycle.  In addition, a 'resetting' state exists which is
# similar to 'draining' except that threads leave with a BrokenBarrierError,
# and a 'broken' state in which all threads get the exception.

class Barrier(object):
    """Implements a Barrier.

    Useful for synchronizing a fixed number of threads at known synchronization
    points.  Threads block on 'wait()' and are simultaneously once they have all
    made that call.

    """

    def __init__(self, parties, action=None, timeout=None):
        """Create a barrier, initialised to 'parties' threads.

        'action' is a callable which, when supplied, will be called by one of
        the threads after they have all entered the barrier and just prior to
        releasing them all. If a 'timeout' is provided, it is uses as the
        default for all subsequent 'wait()' calls.

        """
        self._cond = Condition(Lock())
        self._action = action
        self._timeout = timeout
        self._parties = parties
        self._state = 0   # 0 filling, 1, draining, -1 resetting, -2 broken
        self._count = 0

    def wait(self, timeout=None):
        """Wait for the barrier.

        When the specified number of threads have started waiting, they are all
        simultaneously awoken. If an 'action' was provided for the barrier, one
        of the threads will have executed that callback prior to returning.
        Returns an individual index number from 0 to 'parties-1'.

        """
        if timeout is None:
            timeout = self._timeout
        with self._cond:
            self._enter()    # Block while the barrier drains.
            index = self._count
            self._count += 1
            try:
                if index + 1 == self._parties:
                    # We release the barrier
                    self._release()
                else:
                    # We wait until someone releases us
                    self._wait(timeout)
                return index
            finally:
                self._count -= 1
                # Wake up any threads waiting for barrier to drain.
                self._exit()

    # Block until the barrier is ready for us, or raise an exception
    # if it is broken.
    def _enter(self):
        while self._state in (-1, 1):
            # It is draining or resetting, wait until done
            self._cond.wait()
        #see if the barrier is in a broken state
        if self._state < 0:
            raise BrokenBarrierError
        assert self._state == 0

    # Optionally run the 'action' and release the threads waiting
    # in the barrier.
    def _release(self):
        try:
            if self._action:
                self._action()
            # enter draining state
            self._state = 1
            self._cond.notify_all()
        except:
            #an exception during the _action handler.  Break and reraise
            self._break()
            raise

    # Wait in the barrier until we are relased.  Raise an exception
    # if the barrier is reset or broken.
    def _wait(self, timeout):
        if not self._cond.wait_for(lambda: self._state != 0, timeout):
            #timed out.  Break the barrier
            self._break()
            raise BrokenBarrierError
        if self._state < 0:
            raise BrokenBarrierError
        assert self._state == 1

    # If we are the last thread to exit the barrier, signal any threads
    # waiting for the barrier to drain.
    def _exit(self):
        if self._count == 0:
            if self._state in (-1, 1):
                #resetting or draining
                self._state = 0
                self._cond.notify_all()

    def reset(self):
        """Reset the barrier to the initial state.

        Any threads currently waiting will get the BrokenBarrier exception
        raised.

        """
        with self._cond:
            if self._count > 0:
                if self._state == 0:
                    #reset the barrier, waking up threads
                    self._state = -1
                elif self._state == -2:
                    #was broken, set it to reset state
                    #which clears when the last thread exits
                    self._state = -1
            else:
                self._state = 0
            self._cond.notify_all()

    def abort(self):
        """Place the barrier into a 'broken' state.

        Useful in case of error.  Any currently waiting threads and threads
        attempting to 'wait()' will have BrokenBarrierError raised.

        """
        with self._cond:
            self._break()

    def _break(self):
        # An internal error was detected.  The barrier is set to
        # a broken state all parties awakened.
        self._state = -2
        self._cond.notify_all()

    @property
    def parties(self):
        """Return the number of threads required to trip the barrier."""
        return self._parties

    @property
    def n_waiting(self):
        """Return the number of threads currently waiting at the barrier."""
        # We don't need synchronization here since this is an ephemeral result
        # anyway.  It returns the correct value in the steady state.
        if self._state == 0:
            return self._count
        return 0

    @property
    def broken(self):
        """Return True if the barrier is in a broken state."""
        return self._state == -2


class BrokenBarrierError(RuntimeError):
    pass

