#
# This file is part of Evergreen. See the NOTICE for more information.
#

try:
    from time import monotonic as _time
except ImportError:
    from time import time as _time

from evergreen.event import Event
from evergreen.locks import Condition, Lock
from evergreen.log import log


FIRST_COMPLETED = 'FIRST_COMPLETED'
FIRST_EXCEPTION = 'FIRST_EXCEPTION'
ALL_COMPLETED = 'ALL_COMPLETED'
_AS_COMPLETED = '_AS_COMPLETED'

# Possible future states (for internal use by the futures package).
PENDING = 'PENDING'
RUNNING = 'RUNNING'
# The future was cancelled by the user...
CANCELLED = 'CANCELLED'
# ...and _Waiter.add_cancelled() was called by a worker.
CANCELLED_AND_NOTIFIED = 'CANCELLED_AND_NOTIFIED'
FINISHED = 'FINISHED'

_FUTURE_STATES = [
    PENDING,
    RUNNING,
    CANCELLED,
    CANCELLED_AND_NOTIFIED,
    FINISHED
]

_STATE_TO_DESCRIPTION_MAP = {
    PENDING: "pending",
    RUNNING: "running",
    CANCELLED: "cancelled",
    CANCELLED_AND_NOTIFIED: "cancelled",
    FINISHED: "finished"
}


class Error(Exception):
    """Base class for all future-related exceptions."""
    pass


class CancelledError(Error):
    """The Future was cancelled."""
    pass


class TimeoutError(Error):
    """The operation exceeded the given deadline."""
    pass


class _Waiter(object):
    """Provides the event that wait() and as_completed() block on."""
    def __init__(self):
        self.event = Event()
        self.finished_futures = []

    def add_result(self, future):
        self.finished_futures.append(future)

    def add_exception(self, future):
        self.finished_futures.append(future)

    def add_cancelled(self, future):
        self.finished_futures.append(future)


class _AsCompletedWaiter(_Waiter):
    """Used by as_completed()."""

    def __init__(self):
        super(_AsCompletedWaiter, self).__init__()
        self.lock = Lock()

    def add_result(self, future):
        with self.lock:
            super(_AsCompletedWaiter, self).add_result(future)
            self.event.set()

    def add_exception(self, future):
        with self.lock:
            super(_AsCompletedWaiter, self).add_exception(future)
            self.event.set()

    def add_cancelled(self, future):
        with self.lock:
            super(_AsCompletedWaiter, self).add_cancelled(future)
            self.event.set()


class _FirstCompletedWaiter(_Waiter):
    """Used by wait(return_when=FIRST_COMPLETED)."""

    def add_result(self, future):
        super(_FirstCompletedWaiter, self).add_result(future)
        self.event.set()

    def add_exception(self, future):
        super(_FirstCompletedWaiter, self).add_exception(future)
        self.event.set()

    def add_cancelled(self, future):
        super(_FirstCompletedWaiter, self).add_cancelled(future)
        self.event.set()


class _AllCompletedWaiter(_Waiter):
    """Used by wait(return_when=FIRST_EXCEPTION and ALL_COMPLETED)."""

    def __init__(self, num_pending_calls, stop_on_exception):
        self.num_pending_calls = num_pending_calls
        self.stop_on_exception = stop_on_exception
        self.lock = Lock()
        super(_AllCompletedWaiter, self).__init__()

    def _decrement_pending_calls(self):
        with self.lock:
            self.num_pending_calls -= 1
            if not self.num_pending_calls:
                self.event.set()

    def add_result(self, future):
        super(_AllCompletedWaiter, self).add_result(future)
        self._decrement_pending_calls()

    def add_exception(self, future):
        super(_AllCompletedWaiter, self).add_exception(future)
        if self.stop_on_exception:
            self.event.set()
        else:
            self._decrement_pending_calls()

    def add_cancelled(self, future):
        super(_AllCompletedWaiter, self).add_cancelled(future)
        self._decrement_pending_calls()


class _AcquireFutures(object):
    """A context manager that does an ordered acquire of Future conditions."""

    def __init__(self, futures):
        self.futures = sorted(futures, key=id)

    def __enter__(self):
        for future in self.futures:
            future._condition.acquire()

    def __exit__(self, *args):
        for future in self.futures:
            future._condition.release()


def _create_and_install_waiters(fs, return_when):
    if return_when == _AS_COMPLETED:
        waiter = _AsCompletedWaiter()
    elif return_when == FIRST_COMPLETED:
        waiter = _FirstCompletedWaiter()
    else:
        pending_count = sum(f._state not in [CANCELLED_AND_NOTIFIED, FINISHED] for f in fs)
        if return_when == FIRST_EXCEPTION:
            waiter = _AllCompletedWaiter(pending_count, stop_on_exception=True)
        elif return_when == ALL_COMPLETED:
            waiter = _AllCompletedWaiter(pending_count, stop_on_exception=False)
        else:
            raise ValueError("Invalid return condition: %r" % return_when)

    for f in fs:
        f._waiters.append(waiter)

    return waiter


def as_completed(fs, timeout=None):
    """An iterator over the given futures that yields each as it completes.

    Args:
        fs: The sequence of Futures (possibly created by different Executors) to
            iterate over.
        timeout: The maximum number of seconds to wait. If None, then there
            is no limit on the wait time.

    Returns:
        An iterator that yields the given Futures as they complete (finished or
        cancelled).

    Raises:
        TimeoutError: If the entire result iterator could not be generated
            before the given timeout.
    """
    if timeout is not None:
        end_time = timeout + _time()

    with _AcquireFutures(fs):
        finished = set(f for f in fs if f._state in [CANCELLED_AND_NOTIFIED, FINISHED])
        pending = set(fs) - finished
        waiter = _create_and_install_waiters(fs, _AS_COMPLETED)

    try:
        for future in finished:
            yield future

        while pending:
            if timeout is None:
                wait_timeout = None
            else:
                wait_timeout = end_time - _time()
                if wait_timeout < 0:
                    raise TimeoutError('%d (of %d) futures unfinished' % (len(pending), len(fs)))

            waiter.event.wait(wait_timeout)

            with waiter.lock:
                finished = waiter.finished_futures
                waiter.finished_futures = []
                waiter.event.clear()

            for future in finished:
                yield future
                pending.remove(future)

    finally:
        for f in fs:
            f._waiters.remove(waiter)


def wait(fs, timeout=None, return_when=ALL_COMPLETED):
    """Wait for the futures in the given sequence to complete.

    Args:
        fs: The sequence of Futures (possibly created by different Executors) to
            wait upon.
        timeout: The maximum number of seconds to wait. If None, then there
            is no limit on the wait time.
        return_when: Indicates when this function should return. The options
            are:

            FIRST_COMPLETED - Return when any future finishes or is
                              cancelled.
            FIRST_EXCEPTION - Return when any future finishes by raising an
                              exception. If no future raises an exception
                              then it is equivalent to ALL_COMPLETED.
            ALL_COMPLETED -   Return when all futures finish or are cancelled.

    Returns:
        A 2-tuple of sets. The first set, contains the
        futures that completed (is finished or cancelled) before the wait
        completed. The second set, contains uncompleted futures.
    """
    with _AcquireFutures(fs):
        done = set(f for f in fs if f._state in [CANCELLED_AND_NOTIFIED, FINISHED])
        not_done = set(fs) - done

        if (return_when == FIRST_COMPLETED) and done:
            return (done, not_done)
        elif (return_when == FIRST_EXCEPTION) and done:
            if any(f for f in done if not f.cancelled() and f.exception() is not None):
                return (done, not_done)

        if len(done) == len(fs):
            return (done, not_done)

        waiter = _create_and_install_waiters(fs, return_when)

    waiter.event.wait(timeout)
    for f in fs:
        f._waiters.remove(waiter)

    done.update(waiter.finished_futures)
    return (done, set(fs) - done)


class Future(object):

    def __init__(self):
        self._condition = Condition()
        self._state = PENDING
        self._result = None
        self._exception = None
        self._callbacks = []
        self._waiters = []

    def __repr__(self):
        with self._condition:
            if self._state == FINISHED:
                if self._exception:
                    text = 'raised %s' % self._exception.__class__.__name__
                else:
                    text = 'returned %s' % self._result.__class__.__name__
                return '<%s at %s state=%s %s>' % (
                    self.__class__.__name__,
                    hex(id(self)),
                    _STATE_TO_DESCRIPTION_MAP[self._state],
                    text)
            return '<%s at %s state=%s>' % (
                    self.__class__.__name__,
                    hex(id(self)),
                   _STATE_TO_DESCRIPTION_MAP[self._state])

    def cancel(self):
        with self._condition:
            if self._state in (RUNNING, FINISHED):
                return False
            elif self._state in (CANCELLED, CANCELLED_AND_NOTIFIED):
                return True
            self._state = CANCELLED
            self._condition.notify_all()
        self._run_callbacks()
        return True

    @property
    def cancelled(self):
        with self._condition:
            return self._state in (CANCELLED, CANCELLED_AND_NOTIFIED)

    @property
    def done(self):
        with self._condition:
            return self._state in (CANCELLED, CANCELLED_AND_NOTIFIED, FINISHED)

    def get(self, timeout=None, return_exception=False):
        with self._condition:
            if self._state in (CANCELLED, CANCELLED_AND_NOTIFIED):
                raise CancelledError()
            elif self._state == FINISHED:
                return self._get_result(return_exception)

            self._condition.wait(timeout)

            if self._state in (CANCELLED, CANCELLED_AND_NOTIFIED):
                raise CancelledError()
            elif self._state == FINISHED:
                return self._get_result(return_exception)
            else:
                raise TimeoutError()

    def add_done_callback(self, func):
        with self._condition:
            if self._state not in (CANCELLED, CANCELLED_AND_NOTIFIED, FINISHED):
                self._callbacks.append(func)
                return
        func(self)

    # Internal

    def _get_result(self, return_exception):
        if self._exception:
            if return_exception:
                return self._exception
            else:
                raise self._exception
        else:
            return self._result

    def _run_callbacks(self):
        for cb in self._callbacks:
            try:
                cb(self)
            except Exception:
                log.exception('exception calling callback for %r', self)
        self._callbacks = []

    def set_running_or_notify_cancel(self):
        with self._condition:
            if self._state == CANCELLED:
                self._state = CANCELLED_AND_NOTIFIED
                for waiter in self._waiters:
                    waiter.add_cancelled(self)
                # self._condition.notify_all() is not necessary because
                # self.cancel() triggers a notification.
                return False
            elif self._state == PENDING:
                self._state = RUNNING
                return True
            else:
                raise RuntimeError('Future in unexpected state: %s' % self._state)

    def set_result(self, result):
        with self._condition:
            self._result = result
            self._state = FINISHED
            for waiter in self._waiters:
                waiter.add_result(self)
            self._condition.notify_all()
        self._run_callbacks()

    def set_exception(self, exception):
        with self._condition:
            self._exception = exception
            self._state = FINISHED
            for waiter in self._waiters:
                waiter.add_exception(self)
            self._condition.notify_all()
        self._run_callbacks()


class Executor(object):

    def submit(self, fn, *args, **kwargs):
        """Submits a callable to be executed with the given arguments.

        Schedules the callable to be executed as fn(*args, **kwargs) and returns
        a Future instance representing the execution of the callable.

        Returns:
            A Future representing the given call.
        """
        raise NotImplementedError

    def map(self, fn, *iterables, **kwargs):
        """Returns a iterator equivalent to map(fn, iter).

        Args:
            fn: A callable that will take take as many arguments as there are
                passed iterables.
            timeout: The maximum number of seconds to wait. If None, then there
                is no limit on the wait time.

        Returns:
            An iterator equivalent to: map(func, *iterables) but the calls may
            be evaluated out-of-order.

        Raises:
            TimeoutError: If the entire result iterator could not be generated
                before the given timeout.
            Exception: If fn(*args) raises for any values.
        """
        timeout = kwargs.get('timeout')
        if timeout is not None:
            end_time = timeout + _time()

        fs = [self.submit(fn, *args) for args in zip(*iterables)]

        # Yield must be hidden in closure so that the futures are submitted
        # before the first iterator value is required.
        def result_iterator():
            try:
                for future in fs:
                    if timeout is None:
                        yield future.get()
                    else:
                        yield future.get(end_time - _time())
            finally:
                for future in fs:
                    future.cancel()
        return result_iterator()

    def shutdown(self, wait=True):
        """Clean-up the resources associated with the Executor.

        It is safe to call this method several times. Otherwise, no other
        methods can be called after this one.

        Args:
            wait: If True then shutdown will not return until all running
                futures have finished executing and the resources used by the
                executor have been reclaimed.
        """
        pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.shutdown(wait=True)
        return False


class InfiniteHandler(object):
    """Helper class to create a handler that keeps the loop alive until
    it's cancelled.
    """

    def __init__(self, loop):
        self.loop = loop
        self._cb()

    def _cb(self):
        self.handler = self.loop.call_later(24*3600, self._cb)

    def cancel(self):
        if self.handler:
            self.handler.cancel()
            self.handler = self.loop = None

