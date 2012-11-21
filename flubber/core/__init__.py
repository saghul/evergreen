
from flubber.core.task import Task, TaskExit, get_current
from flubber.core.hub import Hub, get_hub

__all__ = ['Hub', 'Task', 'TaskExit', 'current_ctx', 'spawn', 'spawn_later', 'sleep', 'yield_']


def sleep(seconds=0):
    """Yield control to another eligible coroutine until at least *seconds* have
    elapsed.

    *seconds* may be specified as an integer, or a float if fractional seconds
    are desired.
    """
    hub = get_hub()
    current = get_current()
    timer = hub.call_later(seconds, current.switch)
    try:
        hub.switch()
    finally:
        timer.cancel()


def yield_():
    """Yield control to another eligible coroutine for a loop iteration.

    For example, if one is looping over a large list performing an expensive
    calculation without calling any socket methods, it's a good idea to
    call ``yield_()`` occasionally; otherwise nothing else will run.
    """
    hub = get_hub()
    current = get_current()
    hub.next_tick(current.switch)
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
    hub = get_hub()
    t = Task(target=func, args=args, kwargs=kwargs)
    timer = hub.call_later(seconds, t.start)
    return timer, t


class _CurrentContext(object):

    @property
    def hub(self):
        return get_hub()

    @property
    def task(self):
        return get_current()

current_ctx = _CurrentContext()

