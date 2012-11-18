
import greenlet
import flubber

from flubber.event import Event

__all__ = ['get_current', 'sleep', 'spawn', 'spawn_later', 'Task', 'TaskExit']


get_current = greenlet.getcurrent
TaskExit = greenlet.GreenletExit


def sleep(seconds=0):
    """Yield control to another eligible coroutine until at least *seconds* have
    elapsed.

    *seconds* may be specified as an integer, or a float if fractional seconds
    are desired. Calling :func:`~task.sleep` with *seconds* of 0 is the
    canonical way of expressing a cooperative yield. For example, if one is
    looping over a large list performing an expensive calculation without
    calling any socket methods, it's a good idea to call ``sleep(0)``
    occasionally; otherwise nothing else will run.
    """
    hub = flubber.core.hub
    current = flubber.core.current_greenlet
    timer = hub.call_later(seconds, current.switch)
    try:
        hub.switch()
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


def spawn_later(seconds, func, *args, **kwargs):
    """Spawns *func* after *seconds* have elapsed.

    *seconds* may be specified as an integer, or a float if fractional seconds
    are desired. The *func* will be called with the given *args* and
    keyword arguments *kwargs*, and will be executed within its own task.

    The return value of :func:`spawn_later` is a :class:`Task` object.

    To cancel the spawn and prevent *func* from being called,
    call :meth:`Task.cancel` on the return value of :func:`spawn_after`.
    This will not abort the function if it's already started running, which is
    generally the desired behavior.  If terminating *func* regardless of whether
    it's started or not is the desired behavior, call :meth:`Task.kill`.
    """
    hub = flubber.core.hub
    t = Task(target=func, args=args, kwargs=kwargs)
    timer = hub.call_later(seconds, t.start)
    return timer, t


class Task(greenlet.greenlet):

    def __init__(self, target=None, args=(), kwargs=None):
        greenlet.greenlet.__init__(self, run=self.__run, parent=flubber.core.hub.greenlet)
        if kwargs is None:
            kwargs = {}
        self._target = target
        self._args = args
        self._kwargs = kwargs
        self._exit_event = Event()

    def start(self):
        hub = flubber.core.hub
        hub.next_tick(self.switch)

    def run_(self):
        try:
            if self._target:
                self._target(*self._args, **self._kwargs)
        finally:
            del self._target, self._args, self._kwargs

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
        hub = flubber.core.hub
        current = flubber.core.current_greenlet
        hub.next_tick(current.switch)
        self.throw(*throw_args)

    # internal

    def __run(self):
        try:
            self.run_()
        finally:
            self._exit_event.set()

