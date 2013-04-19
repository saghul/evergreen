#
# This file is part of Evergreen. See the NOTICE for more information.
#

from evergreen.futures._base import Executor, Future
from evergreen.locks import Lock
from evergreen.queue import Queue
from evergreen.tasks import Task


class _WorkItem(object):
    def __init__(self, future, fn, args, kwargs):
        self.future = future
        self.fn = fn
        self.args = args
        self.kwargs = kwargs

    def __call__(self):
        if not self.future.set_running_or_notify_cancel():
            return
        try:
            result = self.fn(*self.args, **self.kwargs)
        except BaseException as e:
            self.future.set_exception(e)
        else:
            self.future.set_result(result)


class TaskPoolExecutor(Executor):

    def __init__(self, max_workers):
        self._max_workers = max_workers
        self._tasks = set()
        self._work_queue = Queue()
        self._shutdown = False
        self._shutdown_lock = Lock()

    def submit(self, fn, *args, **kwargs):
        with self._shutdown_lock:
            if self._shutdown:
                raise RuntimeError('cannot schedule new futures after shutdown')
            f = Future()
            work = _WorkItem(f, fn, args, kwargs)
            self._work_queue.put(work)
            self._adjust_task_count()
            return f

    def shutdown(self, wait=True):
        with self._shutdown_lock:
            self._shutdown = True
            self._work_queue.put(None)
        if wait:
            for task in self._tasks:
                task.join()

    def _adjust_task_count(self):
        if len(self._tasks) < self._max_workers:
            t = Task(self._work)
            self._tasks.add(t)
            t.start()

    def _work(self):
        while True:
            work_item = self._work_queue.get(block=True)
            if work_item is not None:
                work_item()
                del work_item
                continue
            if self._shutdown:
                # Notice other workers
                self._work_queue.put(None)
                return

