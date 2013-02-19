# -*- coding: utf-8 -
#
# This file is part of flubber. See the NOTICE for more information.

import flubber

from flubber.event import Event
from flubber._tasklet import tasklet, get_current, TaskletExit

__all__ = ['Task', 'TaskExit', 'get_current', 'spawn', 'sleep', 'yield_']


def sleep(seconds=0):
    """Yield control to another eligible coroutine until at least *seconds* have
    elapsed.

    *seconds* may be specified as an integer, or a float if fractional seconds
    are desired.
    """
    hub = flubber.current.hub
    current = get_current()
    assert hub.tasklet is not current
    timer = hub.call_later(seconds, current.switch)
    try:
        hub.switch()
    finally:
        timer.cancel()


def yield_():
    """Yield control to another eligible coroutine for a short period of time.

    For example, if one is looping over a large list performing an expensive
    calculation without calling any socket methods, it's a good idea to
    call ``yield_()`` occasionally; otherwise nothing else will run.
    """
    hub = flubber.current.hub
    current = get_current()
    assert hub.tasklet is not current
    hub.call_soon(current.switch)
    hub.switch()


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


TaskExit = TaskletExit

class Task(tasklet):

    def __init__(self, target=None, args=(), kwargs={}):
        super(Task, self).__init__(parent=flubber.current.hub.tasklet)
        self._target = target
        self._args = args
        self._kwargs = kwargs
        self._started = False
        self._exit_event = Event()

    def start(self):
        if self._started:
            raise RuntimeError('tasks can only be started once')
        self._started = True
        hub = flubber.current.hub
        hub.call_soon(self.switch)

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

        Calling :func:`kill` causes the calling task to cooperatively yield.
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
        hub = flubber.current.hub
        current = flubber.current.task
        hub.call_soon(current.switch)
        self.throw(*throw_args)

    # internal

    def run(self):
        try:
            self.run_()
        finally:
            del self._target, self._args, self._kwargs
            self._exit_event.set()

