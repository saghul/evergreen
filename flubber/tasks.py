#
# This file is part of flubber. See the NOTICE for more information.
#

import flubber

from flubber.event import Event
from flubber._tasklet import tasklet, get_current, TaskletExit

__all__ = ['Task', 'TaskExit', 'spawn', 'sleep', 'task']


def sleep(seconds=0):
    """Yield control to another eligible coroutine until at least *seconds* have
    elapsed.

    *seconds* may be specified as an integer, or a float if fractional seconds
    are desired.
    """
    loop = flubber.current.loop
    current = get_current()
    assert loop.tasklet is not current
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


TaskExit = TaskletExit


# Helper to generate new thread names
_counter = 0
def _newname(template="Task-%d"):
    global _counter
    _counter = _counter + 1
    return template % _counter


class Task(tasklet):

    def __init__(self, target=None, name=None, args=(), kwargs={}):
        super(Task, self).__init__(parent=flubber.current.loop.tasklet)
        self._name = str(name or _newname())
        self._target = target
        self._args = args
        self._kwargs = kwargs
        self._started = False
        self._exit_event = Event()

    def start(self):
        if self._started:
            raise RuntimeError('tasks can only be started once')
        self._started = True
        flubber.current.loop.call_soon(self.switch)

    def run_(self):
        if self._target:
            self._target(*self._args, **self._kwargs)

    def join(self, timeout=None):
        """Wait for this Task to end. If a timeout is given, after the time expires the function
        will return anyway."""
        return self._exit_event.wait(timeout)

    def kill(self, *throw_args):
        """Terminates the current task by raising an exception into it.
        Whatever that task might be doing; be it waiting for I/O or another
        primitive, it sees an exception as soon as it yields control.

        By default, this exception is TaskExit, but a specific exception
        may be specified.  *throw_args* should be the same as the arguments to
        raise; either an exception instance or an exc_info tuple.

        """
        if self.dead:
            return
        if not self:
            # task hasn't started yet and therefore throw won't work
            def just_raise(*a, **kw):
                if throw_args:
                    raise throw_args[0], throw_args[1], throw_args[2]
                else:
                    raise TaskExit()
            self.run_ = just_raise
            return
        flubber.current.loop.call_soon(self.throw, *throw_args)

    def __repr__(self):
        status = "initial"
        if self._started:
            status = "started"
        if self.dead:
            status = "dead"
        if self._exit_event.is_set():
            status = "ended"
        return "<%s(%s, %s)>" % (self.__class__.__name__, self._name, status)

    @property
    def name(self):
        return self._name

    # internal

    def switch(self, *args, **kwargs):
        current = flubber.current.task
        if current is not flubber.current.loop.tasklet:
            raise RuntimeError('only the loop tasklet can switch to a Task')
        return super(Task, self).switch(*args, **kwargs)

    def throw(self, *args):
        current = flubber.current.task
        if current is not flubber.current.loop.tasklet:
            raise RuntimeError('only the loop tasklet can throw to a Task')
        return super(Task, self).throw(*args)

    def run(self):
        try:
            self.run_()
        finally:
            del self._target, self._args, self._kwargs
            self._exit_event.set()

