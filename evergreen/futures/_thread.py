#
# This file is part of Evergreen. See the NOTICE for more information.
#

import atexit
import threading
import weakref

import evergreen
from evergreen.futures._base import Executor, Future
from evergreen.six.moves import queue


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
        self.loop = evergreen.current.loop
        # Keep the loop alive while this work item is queued
        self.handler = self.loop.call_repeatedly(24*3600, lambda: None)
        self._event = threading.Event()
        self._result = None
        self._exc = None
        self._cancelled = False

    def run(self):
        self.loop.call_from_thread(self._set_running)
        self._event.wait()
        if self._cancelled:
            return
        try:
            r = self.fn(*self.args, **self.kwargs)
            self.loop.call_from_thread(self.future.set_result, r)
        except BaseException as e:
            self.loop.call_from_thread(self.future.set_exception, e)
        finally:
            self.loop.call_from_thread(self.handler.cancel)
            self.loop = self.handler = None

    def _set_running(self):
        if not self.future.set_running_or_notify_cancel():
            self.handler.cancel()
            self._cancelled = True
        self._event.set()

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

