
import sys
import os

from eventlet import patcher
from eventlet.support import greenlets as greenlet

__all__ = ["get_hub", "trampoline"]

threading = patcher.original('threading')
_threadlocal = threading.local()


def get_hub():
    """Get the current event hub singleton object.

    .. note :: |internal|
    """
    from eventlet.hubs.pyuv import Hub
    try:
        hub = _threadlocal.hub
    except AttributeError:
        _threadlocal.Hub = Hub
        hub = _threadlocal.hub = _threadlocal.Hub()
    return hub


def trampoline(fd, read=None, write=None, timeout=None, timeout_exc=None):
    """Suspend the current coroutine until the given socket object or file
    descriptor is ready to *read*, ready to *write*, or the specified
    *timeout* elapses, depending on arguments specified.

    To wait for *fd* to be ready to read, pass *read* ``=True``; ready to
    write, pass *write* ``=True``. To specify a timeout, pass the *timeout*
    argument in seconds.

    If the specified *timeout* elapses before the socket is ready to read or
    write, *timeout_exc* will be raised instead of ``trampoline()``
    returning normally.

    .. note :: |internal|
    """
    from eventlet.timeout import Timeout
    timeout_exc = timeout_exc or Timeout
    t = None
    hub = get_hub()
    current = greenlet.getcurrent()
    assert hub.greenlet is not current, 'do not call blocking functions from the mainloop'
    assert not (read and write), 'not allowed to trampoline for reading and writing'
    try:
        fileno = fd.fileno()
    except AttributeError:
        fileno = fd
    if timeout is not None:
        t = hub.schedule_call_global(timeout, current.throw, timeout_exc)
    try:
        if read:
            listener = hub.add(hub.READ, fileno, current.switch)
        elif write:
            listener = hub.add(hub.WRITE, fileno, current.switch)
        try:
            return hub.switch()
        finally:
            hub.remove(listener)
    finally:
        if t is not None:
            t.cancel()

