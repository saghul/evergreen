
import pyuv
import traceback

from collections import deque
from functools import partial
from greenlet import greenlet, getcurrent, GreenletExit

from eventlet import patcher
from eventlet.futures import Future
from eventlet.timeout import Timeout
from eventlet.threadpool import ThreadPool

__all__ = ["get_hub", "trampoline"]


threading = patcher.original('threading')
_threadlocal = threading.local()


def get_hub():
    """Get the current event hub singleton object.
    """
    try:
        hub = _threadlocal.hub
    except AttributeError:
        hub = _threadlocal.hub = Hub()
    return hub


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


class _SchedulledCall(object):

    def __init__(self, future, func, args, kwargs):
        self.future = future
        self.cb = partial(func, *args, **kwargs)

    def __call__(self):
        if not self.future.set_running_or_notify_cancel():
            return
        try:
            result = self.cb()
        except BaseException as e:
            self.future.set_exception(e)
        else:
            self.future.set_result(result)


class Hub(object):
    SYSTEM_ERROR = (KeyboardInterrupt, SystemExit, SystemError)
    NOT_ERROR = (GreenletExit, SystemExit)

    def __init__(self):
        self.greenlet = greenlet(self.run)
        self.loop = pyuv.Loop()
        self.loop.excepthook = self.handle_error
        self.listeners = {pyuv.UV_READABLE: {}, pyuv.UV_WRITABLE: {}}
        self.threadpool = ThreadPool(self)

        self._timers = set()
        self._waker = Waker(self)
        self._tick_prepare = pyuv.Prepare(self.loop)
        self._tick_idle = pyuv.Idle(self.loop)
        self._tick_callbacks = deque()

        self.stopping = False
        self.running = False

    def switch(self):
        current = getcurrent()
        assert current is not self.greenlet, 'Cannot switch to MAINLOOP from MAINLOOP'
        switch_out = getattr(current, 'switch_out', None)
        if switch_out is not None:
            switch_out()
        if self.greenlet.dead:
            self.greenlet = greenlet(self.run)
        try:
            if self.greenlet.parent is not current:
                current.parent = self.greenlet
        except ValueError:
            pass  # gets raised if there is a greenlet parent cycle
        return self.greenlet.switch()

    def next_tick(self, func, *args, **kw):
        self._tick_callbacks.append(partial(func, *args, **kw))
        if not self._tick_prepare.active:
            self._tick_prepare.start(self._tick_cb)
            self._tick_idle.start(lambda handle: handle.stop())

    def schedulle_call(self, func, *args, **kw):
        future = Future()
        item = _SchedulledCall(future, func, args, kw)
        self._tick_callbacks.append(item)
        if not self._tick_prepare.active:
            self._tick_prepare.start(self._tick_cb)
            self._tick_idle.start(lambda handle: handle.stop())
        return future

    def run(self, *a, **kw):
        """Run the runloop until abort is called.
        """
        # accept and discard variable arguments because they will be
        # supplied if other greenlets have run and exited before the
        # hub's greenlet gets a chance to run
        if self.running:
            raise RuntimeError("Already running!")
        try:
            self.running = True
            while not self.stopping:
                self.loop.run_once()
        finally:
            self.running = False
            self.stopping = False
            # TODO
            #self._waker = None
            #self._cleanup_loop()

    def abort(self, wait=False):
        """Stop the runloop. If run is executing, it will exit after
        completing the next runloop iteration.

        Set *wait* to True to cause abort to switch to the hub immediately and
        wait until it's finished processing.  Waiting for the hub will only
        work from the main greenthread; all other greenthreads will become
        unreachable.
        """
        if self.running:
            self.stopping = True
        if wait:
            assert self.greenlet is not getcurrent(), "Can't abort with wait from inside the hub's greenlet."
            # wakeup loop, in case it was busy polling
            self._waker.wake()
            self.switch()

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

    def handle_error(self, typ, value, tb):
        if not issubclass(type, self.NOT_ERROR):
            traceback.print_exception(typ, value, tb)
        if issubclass(type, self.SYSTEM_ERROR):
            current = getcurrent()
            if current is self.greenlet:
                self.greenlet.parent.throw(typ, value)
            else:
                # TODO: maybe next_tick is not such a good idea
                self.next_tick(self.parent.throw, typ, value)
        del tb

    # private

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

