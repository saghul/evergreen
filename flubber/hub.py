
import pyuv
import traceback

from collections import deque
from functools import partial
from greenlet import greenlet, getcurrent, GreenletExit

from flubber import patcher
from flubber.timeout import Timeout
from flubber.threadpool import ThreadPool

__all__ = ["get_hub", "trampoline"]


threading = patcher.original('threading')
_tls = threading.local()


def get_hub():
    """Get the current event hub singleton object.
    """
    try:
        return _tls.hub
    except AttributeError:
        raise RuntimeError('there is no hub created in the current thread')


def trampoline(fd, read=False, write=False, timeout=None, timeout_exc=None):
    """Suspend the current coroutine until the given socket object or file
    descriptor is ready to *read*, ready to *write*, or the specified
    *timeout* elapses, depending on arguments specified.

    To wait for *fd* to be ready to read, pass *read* ``=True``; ready to
    write, pass *write* ``=True``. To specify a timeout, pass the *timeout*
    argument in seconds.

    If the specified *timeout* elapses before the socket is ready to read or
    write, *timeout_exc* will be raised instead of ``trampoline()``
    returning normally.
    """
    hub = get_hub()
    return hub.wait_fd(fd, read, write, timeout, timeout_exc)


class FDListener(object):
    evtype_map = {pyuv.UV_READABLE: 'read', pyuv.UV_WRITABLE: 'write'}

    def __init__(self, hub, evtype, fileno, cb):
        assert (evtype == pyuv.UV_READABLE or evtype == pyuv.UV_WRITABLE)
        self.evtype = evtype
        self.fd = fileno
        self.cb = cb
        self._handle = pyuv.Poll(hub.loop, fileno)

    def start(self):
        self._handle.start(self.evtype, self._poll_cb)

    def stop(self):
        self._handle.stop()

    def _poll_cb(self, handle, events, error):
        self.cb()

    def __repr__(self):
        return "%s(%r, %r, %r)" % (type(self).__name__, self.evtype_map[self.evtype], self.fileno, self.cb)


class Waker(object):

    def __init__(self, hub):
        self._async = pyuv.Async(hub.loop, lambda x: None)
        self._async.unref()

    def wake(self):
        self._async.send()


class Hub(object):
    SYSTEM_ERROR = (KeyboardInterrupt, SystemExit, SystemError)
    NOT_ERROR = (GreenletExit, SystemExit)

    def __init__(self):
        global _tls
        if getattr(_tls, 'hub', None) is not None:
            raise RuntimeError('cannot instantiate more than one Hub per thread')
        _tls.hub = self
        self.greenlet = greenlet(self._run_loop)
        self.loop = pyuv.Loop()
        self.loop.excepthook = self._handle_error
        self.listeners = {pyuv.UV_READABLE: {}, pyuv.UV_WRITABLE: {}}
        self.threadpool = ThreadPool(self)

        self._timers = set()
        self._waker = Waker(self)
        self._signal_checker = pyuv.SignalChecker(self.loop)
        self._tick_prepare = pyuv.Prepare(self.loop)
        self._tick_idle = pyuv.Idle(self.loop)
        self._tick_callbacks = deque()

    def switch(self):
        current = getcurrent()
        switch_out = getattr(current, 'switch_out', None)
        if switch_out is not None:
            switch_out()
        try:
            if self.greenlet.parent is not current:
                current.parent = self.greenlet
        except ValueError:
            pass  # gets raised if there is a greenlet parent cycle
        return self.greenlet.switch()

    def switch_out(self):
        raise RuntimeError('Cannot switch to MAINLOOP from MAINLOOP')

    def next_tick(self, func, *args, **kw):
        self._tick_callbacks.append(partial(func, *args, **kw))
        if not self._tick_prepare.active:
            self._tick_prepare.start(self._tick_cb)
            self._tick_idle.start(lambda handle: handle.stop())

    def run(self):
        current = getcurrent()
        if current is not self.greenlet.parent:
            raise RuntimeError('run() can only be called from MAIN greenlet')
        if self.greenlet.dead:
            return
        self.greenlet.switch()

    def destroy(self):
        global _tls
        if getattr(_tls, 'hub', None) is not self:
            raise RuntimeError('destroy() can only be called from the same thread were the hub was created')
        del _tls.hub

        self._cleanup_loop()
        self.loop.excepthook = None
        self.loop = None
        self.listeners = None
        self.threadpool = None

        self._timers = None
        self._waker = None
        self._signal_checker = None
        self._tick_prepare = None
        self._tick_idle = None
        self._tick_callbacks = None

    def call_later(self, seconds, cb, *args, **kw):
        """Schedule a callable to be called after 'seconds' seconds have
        elapsed. The timer will NOT be canceled if the current greenlet has
        exited before the timer fires.
            seconds: The number of seconds to wait.
            cb: The callable to call after the given time.
            *args: Arguments to pass to the callable when called.
            **kw: Keyword arguments to pass to the callable when called.
        """
        return _Timer(self, seconds, cb, *args, **kw)

    def wait_fd(self, fd, read=False, write=False, timeout=None, timeout_exc=None):
        timeout_exc = timeout_exc or Timeout
        current = getcurrent()
        assert not (read and write), 'not allowed to trampoline for reading and writing'
        assert any((read, write)), 'either read or write event needs to be specified'
        try:
            fileno = fd.fileno()
        except AttributeError:
            fileno = fd
        if timeout is not None:
            t = self.call_later(timeout, current.throw, timeout_exc)
        try:
            event = pyuv.UV_READABLE if read else pyuv.UV_WRITABLE
            listener = FDListener(self, event, fileno, current.switch)
            self._add_listener(listener)
            try:
                return self.switch()
            finally:
                self._remove_listener(listener)
        finally:
            if timeout is not None:
                t.cancel()

    # internal

    def _handle_error(self, typ, value, tb):
        if not issubclass(typ, self.NOT_ERROR):
            traceback.print_exception(typ, value, tb)
        if issubclass(typ, self.SYSTEM_ERROR):
            current = getcurrent()
            if current is self.greenlet:
                self.greenlet.parent.throw(typ, value)
            else:
                self.next_tick(self.parent.throw, typ, value)
        del tb

    def _run_loop(self):
        self._signal_checker.start()
        try:
            self.loop.run()
        finally:
            self._cleanup_loop()

    def _add_listener(self, listener):
        for evtype in self.listeners.iterkeys():
            if listener.fd in self.listeners[evtype]:
                raise RuntimeError('listener already registered for %s events for fd %d' % (FDListener.evtype_map[evtype], listener.fd))
        self.listeners[listener.evtype][listener.fd] = listener
        listener.start()

    def _remove_listener(self, listener):
        listener.stop()
        self.listeners[listener.evtype].pop(listener.fd, None)

    def _cleanup_loop(self):
        def cb(handle):
            if not handle.closed:
                handle.close()
        self.loop.walk(cb)
        # All handles are now closed, run will not block
        self.loop.run()

    def _tick_cb(self, handle):
        self._tick_prepare.stop()
        self._tick_idle.stop()
        queue, self._tick_callbacks = self._tick_callbacks, deque()
        for f in queue:
            f()


class _Timer(object):

    def __init__(self, hub, seconds, cb, *args, **kw):
        self.called = False
        self.cb = partial(cb, *args, **kw)
        hub._timers.add(self)
        self._timer = pyuv.Timer(hub.loop)
        self._timer.start(self._timer_cb, seconds, 0.0)

    def _timer_cb(self, timer):
        if not self.called:
            self.called = True
            try:
                self.cb()
            finally:
                self.cb = None
                self._timer.close()
                self._timer = None
                hub = get_hub()
                hub._timers.remove(self)

    @property
    def pending(self):
        return not self.called

    def cancel(self):
        if not self.called:
            self.called = True
            self._timer.close()
            self._timer = None
            hub = get_hub()
            hub._timers.remove(self)

