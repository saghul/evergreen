#
# This file is part of Evergreen. See the NOTICE for more information.
#

import six

import evergreen
from evergreen.event import Event

from fibers import Fiber


__all__ = ['Task', 'TaskExit', 'spawn', 'sleep', 'task']


def sleep(seconds=0):
    """Yield control to another eligible coroutine until at least *seconds* have
    elapsed.

    *seconds* may be specified as an integer, or a float if fractional seconds
    are desired.
    """
    loop = evergreen.current.loop
    current = Fiber.current()
    assert loop.task is not current
    timer = loop.call_later(seconds, current.switch)
    try:
        loop.switch()
    finally:
        timer.cancel()


def spawn(func, *args, **kwargs):
    """Create a task to run ``func(*args, **kwargs)``.  Returns a
    :class:`Task` objec.

    Execution control returns immediately to the caller; the created task
    is merely scheduled to be run at the next available opportunity.
    Use :func:`spawn_later` to  arrange for tasks to be spawned
    after a finite delay.
    """
    t = Task(target=func, args=args, kwargs=kwargs)
    t.start()
    return t


def task(func):
    """Decorator to run the decorated function as a Task
    """
    def task_wrapper(*args, **kwargs):
        return spawn(func, *args, **kwargs)
    return task_wrapper


class TaskExit(BaseException):
    pass


# Helper to generate new task names
_counter = 0
def _newname(template="Task-%d"):
    global _counter
    _counter = _counter + 1
    return template % _counter


class Task(Fiber):

    def __init__(self, target=None, name=None, args=(), kwargs={}):
        super(Task, self).__init__(target=self.__run, parent=evergreen.current.loop.task)
        self._name = str(name or _newname())
        self._target = target
        self._args = args
        self._kwargs = kwargs
        self._started = False
        self._running = False
        self._exit_event = Event()

    def start(self):
        if self._started:
            raise RuntimeError('tasks can only be started once')
        self._started = True
        evergreen.current.loop.call_soon(self.switch)

    def run(self):
        if self._target:
            self._target(*self._args, **self._kwargs)

    def join(self, timeout=None):
        """Wait for this Task to end. If a timeout is given, after the time expires the function
        will return anyway."""
        if not self._started:
            raise RuntimeError('cannot join task before it is started')
        return self._exit_event.wait(timeout)

    def kill(self, typ=TaskExit, value=None, tb=None):
        """Terminates the current task by raising an exception into it.
        Whatever that task might be doing; be it waiting for I/O or another
        primitive, it sees an exception as soon as it yields control.

        By default, this exception is TaskExit, but a specific exception
        may be specified.
        """
        if not self.is_alive():
            return
        if not value:
            value = typ()
        if not self._running:
            # task hasn't started yet and therefore throw won't work
            def just_raise():
                six.reraise(typ, value, tb)
            self.run = just_raise
            return
        evergreen.current.loop.call_soon(self.throw, typ, value, tb)

    def __repr__(self):
        status = "initial"
        if self._started:
            status = "started"
        if self._running:
            status = "running"
        if self._exit_event.is_set():
            status = "ended"
        return "<%s(%s, %s)>" % (self.__class__.__name__, self._name, status)

    @property
    def name(self):
        return self._name

    # internal

    def __run(self):
        try:
            self._running = True
            self.run()
        except TaskExit:
            pass
        finally:
            self._running = False
            del self._target, self._args, self._kwargs
            self._exit_event.set()

