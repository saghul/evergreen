
import six

from eventlet.lock import Condition


# TODO: add rest of concurrent.futures API


# Possible future states (for internal use by the futures package).
PENDING = 'PENDING'
RUNNING = 'RUNNING'
# The future was cancelled by the user...
CANCELLED = 'CANCELLED'
# ...and _Waiter.add_cancelled() was called by a worker.
CANCELLED_AND_NOTIFIED = 'CANCELLED_AND_NOTIFIED'
FINISHED = 'FINISHED'


class Error(Exception):
    """Base class for all future-related exceptions."""
    pass


class CancelledError(Error):
    """The Future was cancelled."""
    pass


class TimeoutError(Error):
    """The operation exceeded the given deadline."""
    pass


class Future(object):

    def __init__(self):
        self._condition = Condition()
        self._state = PENDING
        self._result = None
        self._exception = None
        self._callbacks = []

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

    def cancelled(self):
        with self._condition:
            return self._state in (CANCELLED, CANCELLED_AND_NOTIFIED)

    def running(self):
        with self._condition:
            return self._state == RUNNING

    def done(self):
        with self._condition:
            return self._state in (CANCELLED, CANCELLED_AND_NOTIFIED, FINISHED)

    def result(self, timeout=None):
        with self._condition:
            if self._state in (CANCELLED, CANCELLED_AND_NOTIFIED):
                raise CancelledError()
            elif self._state == FINISHED:
                return self._get_result()

            self._condition.wait(timeout)

            if self._state in (CANCELLED, CANCELLED_AND_NOTIFIED):
                raise CancelledError()
            elif self._state == FINISHED:
                return self._get_result()
            else:
                raise TimeoutError()

    def exception(self, timeout=None):
        with self._condition:
            if self._state in (CANCELLED, CANCELLED_AND_NOTIFIED):
                raise CancelledError()
            elif self._state == FINISHED:
                return self._exception

            self._condition.wait(timeout)

            if self._state in (CANCELLED, CANCELLED_AND_NOTIFIED):
                raise CancelledError()
            elif self._state == FINISHED:
                return self._exception
            else:
                raise TimeoutError()

    def add_done_callback(self, func):
        with self._condition:
            if self._state not in (CANCELLED, CANCELLED_AND_NOTIFIED, FINISHED):
                self._callbacks.append(func)
                return
        func(self)

    # Internal

    def _get_result(self):
        if self._exception:
            if isinstance(self._exception, tuple):
                six.reraise(*self._exception)
            else:
                raise self._exception
        else:
            return self._result

    def _run_callbacks(self):
        for cb in self._callbacks:
            try:
                cb(self)
            except Exception:
                pass
        self._callbacks = []

    def set_running_or_notify_cancel(self):
        with self._condition:
            if self._state == CANCELLED:
                self._state = CANCELLED_AND_NOTIFIED
                # self._condition.notify_all() is not necessary because
                # self.cancel() triggers a notification.
                return False
            elif self._state == PENDING:
                self._state = RUNNING
                return True
            else:
                raise RuntimeError('Future in unexpected state')

    def set_result(self, result):
        with self._condition:
            self._result = result
            self._state = FINISHED
            self._condition.notify_all()
        self._run_callbacks()

    def set_exception(self, exception):
        with self._condition:
            self._exception = exception
            self._state = FINISHED
            self._condition.notify_all()
        self._run_callbacks()

