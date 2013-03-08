#
# This file is part of flubber. See the NOTICE for more information.
#

import atexit
import threading
import weakref
import sys

import flubber
import pyuv
import six

if six.PY3:
    import queue
else:
    import Queue as queue

from flubber.futures._base import Executor, Future


# Workers are created as daemon threads. This is done to allow the interpreter
# to exit when there are still idle threads in a ThreadPoolExecutor's thread
# pool (i.e. shutdown() was not called). However, allowing workers to die with
# the interpreter has two undesirable properties:
#   - The workers would still be running during interpretor shutdown,
#     meaning that they would fail in unpredictable ways.
#   - The workers could be killed while evaluating a work item, which could
#     be bad if the callable being evaluated has external side-effects e.g.
#     writing to a file.
#
# To work around this problem, an exit handler is installed which tells the
# workers to exit when their work queues are empty and then waits until the
# threads finish.

_thread_references = set()
_shutdown = False


def _python_exit():
    global _shutdown
    _shutdown = True
    for thread_reference in _thread_references:
        thread = thread_reference()
        if thread is not None:
            thread.join()


def _remove_dead_thread_references():
    """Remove inactive threads from _thread_references.

    Should be called periodically to prevent memory leaks in scenarios such as:
    >>> while True:
    ...    t = ThreadPoolExecutor(max_workers=5)
    ...    t.map(int, ['1', '2', '3', '4', '5'])
    """
    for thread_reference in set(_thread_references):
        if thread_reference() is None:
            _thread_references.discard(thread_reference)


atexit.register(_python_exit)


class _WorkItem(object):
    def __init__(self, future, fn, args, kwargs):
        self.future = future
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self._async = pyuv.Async(flubber.current.loop._loop, self._async_cb)
        self._event = threading.Event()
        self._result = None
        self._exc = None
        self._cancelled = False

    def run(self):
        self._async.send()
        self._event.wait()
        if self._cancelled:
            return
        try:
            self._result = self.fn(*self.args, **self.kwargs)
        except BaseException:
            self._exc = sys.exc_info()[1]
        finally:
            self._async.send()

    def _async_cb(self, handle):
        if not self._event.is_set():
            if not self.future.set_running_or_notify_cancel():
                self._async.close()
                self._cancelled = True
                self._event.set()
                return
            self._event.set()
        else:
            self._async.close()
            if self._exc is not None:
                self.future.set_exception(self._exc)
            else:
                self.future.set_result(self._result)
            self._result = self._exc = None


def _worker(executor_reference, work_queue):
    while True:
        try:
            work_item = work_queue.get(block=True, timeout=0.1)
        except queue.Empty:
            executor = executor_reference()
            # Exit if:
            #   - The interpreter is shutting down OR
            #   - The executor that owns the worker has been collected OR
            #   - The executor that owns the worker has been shutdown.
            if _shutdown or executor is None or executor._shutdown:
                return
            del executor
        else:
            work_item.run()
            del work_item


class ThreadPoolExecutor(Executor):

    def __init__(self, max_workers):
        _remove_dead_thread_references()

        self._max_workers = max_workers
        self._work_queue = queue.Queue()
        self._threads = set()
        self._shutdown = False
        self._shutdown_lock = threading.Lock()

    def submit(self, fn, *args, **kwargs):
        with self._shutdown_lock:
            if self._shutdown:
                raise RuntimeError('cannot schedule new futures after shutdown')
            f = Future()
            w = _WorkItem(f, fn, args, kwargs)
            self._work_queue.put(w)
            self._adjust_thread_count()
            return f
    submit.__doc__ = Executor.submit.__doc__

    def _adjust_thread_count(self):
        if len(self._threads) < self._max_workers:
            t = threading.Thread(target=_worker, args=(weakref.ref(self), self._work_queue))
            t.daemon = True
            t.start()
            self._threads.add(t)
            _thread_references.add(weakref.ref(t))

    def shutdown(self, wait=True):
        with self._shutdown_lock:
            self._shutdown = True
        if wait:
            for t in self._threads:
                t.join()
    shutdown.__doc__ = Executor.shutdown.__doc__

