
import flubber

from flubber.core._greenlet import greenlet, get_current, GreenletExit
from flubber.event import Event

__all__ = ['get_current', 'Task', 'TaskExit']


TaskExit = GreenletExit


class Task(greenlet):

    def __init__(self, target=None, args=(), kwargs=None):
        greenlet.__init__(self, run=self.__run, parent=flubber.current.hub.greenlet)
        if kwargs is None:
            kwargs = {}
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
        hub = flubber.current.hub
        current = flubber.current.task
        hub.next_tick(current.switch)
        self.throw(*throw_args)

    # internal

    def __run(self):
        try:
            self.run_()
        finally:
            self._exit_event.set()

