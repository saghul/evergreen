
from __future__ import absolute_import

import functools
import pyuv
import sys

from eventlet import patcher
time = patcher.original('time')
from eventlet.hubs.hub import BaseHub, READ, WRITE
from eventlet.support import greenlets as greenlet, clear_sys_exc_info


class _Timer(object):
    def __init__(self, hub, seconds, cb, *args, **kw):
        self.called = False
        self.cb = functools.partial(cb, *args, **kw)
        self._hub = hub
        self._hub._timers.add(self)
        self._timer = pyuv.Timer(hub._loop)
        self._timer.start(self._timer_cb, seconds, 0.0)

    def _timer_cb(self, timer):
        if not self.called:
            self.called = True
            try:
                self.cb()
            except self._hub.SYSTEM_EXCEPTIONS:
                raise
            except:
                self._hub.squelch_timer_exception(self, sys.exc_info())
                clear_sys_exc_info()
            finally:
                self.cb = None
                self._timer.close()
                self._timer = None
                self._hub._timers.remove(self)
                self._hub = None

    @property
    def pending(self):
        return not self.called

    def schedule(self):
        raise NotImplementedError

    def cancel(self):
        if not self.called:
            self.called = True
            self._timer.close()
            self._timer = None
            self._hub._timers.remove(self)
            self._hub = None


class _LocalTimer(_Timer):
    def __init__(self, hub, seconds, cb, *args, **kw):
        self.greenlet = greenlet.getcurrent()
        super(_LocalTimer, self).__init__(hub, seconds, cb, *args, **kw)

    @property
    def pending(self):
        if self.greenlet is None or self.greenlet.dead:
            return False
        return not self.called

    def _timer_cb(self, timer):
        if not self.called:
            self.called = True
            if self.greenlet is not None and self.greenlet.dead:
                return
            try:
                self.cb()
            except self._hub.SYSTEM_EXCEPTIONS:
                raise
            except:
                self._hub.squelch_timer_exception(self, sys.exc_info())
                clear_sys_exc_info()
            finally:
                self.cb = None
                self._timer.close()
                self._timer = None
                self._hub._timers.remove(self)
                self._hub = None

    def cancel(self):
        self.greenlet = None
        super(_LocalTimer, self).cancel()


class Waker(object):

    def __init__(self, hub):
        self._async = pyuv.Async(hub._loop, lambda x: None)
        self._async.unref()

    def wake(self):
        self._async.send()


class Hub(BaseHub):

    def __init__(self):
        super(Hub, self).__init__()
        self._loop = pyuv.Loop()
        self._timers = set()
        self.stopping = False
        self._poll_handles = {}
        self._waker = Waker(self)

    def add(self, evtype, fileno, cb):
        listener = super(Hub, self).add(evtype, fileno, cb)
        self._add_poll_handle(listener)
        return listener

    def remove(self, listener):
        self._remove_poll_handle(listener)
        super(Hub, self).remove(listener)

#    def remove_descriptor(self, fileno):
#        pass

    def run(self):
        if self.running:
            raise RuntimeError("Already running!")
        try:
            self.running = True
            while not self.stopping:
                try:
                    self._loop.run_once()
                #except greenlet.GreenletExit:
                #    break
                except self.SYSTEM_EXCEPTIONS:
                    raise
                except:
                    import traceback
                    traceback.print_exc()
        finally:
            self.running = False
            self.stopping = False
            # TODO
            #self._waker = None
            #self._cleanup_loop()

    def abort(self, wait=False):
        if self.running:
            self.stopping = True
        if wait:
            assert self.greenlet is not greenlet.getcurrent(), "Can't abort with wait from inside the hub's greenlet."
            self._waker.wake()
            self.switch()

    def schedule_call_local(self, seconds, cb, *args, **kw):
        current = greenlet.getcurrent()
        if current is self.greenlet:
            return self.schedule_call_global(seconds, cb, *args, **kw)
        timer = _LocalTimer(self, seconds, cb, *args, **kw)
        return timer

    def schedule_call_global(self, seconds, cb, *args, **kw):
        timer = _Timer(self, seconds, cb, *args, **kw)
        return timer

    def _cleanup_loop(self):
        def cb(handle):
            if not handle.closed:
                handle.close()
        self._loop.walk(cb)
        # All handles are now closed, run will not block
        self._loop.run()

    def _poll_cb(self, listener, handle, error):
        try:
            listener.cb(listener.fileno)
        except self.SYSTEM_EXCEPTIONS:
            raise
        except:
            self.squelch_exception(fileno, sys.exc_info())
            clear_sys_exc_info()

    def _add_poll_handle(self, listener):
        handle = pyuv.Poll(self._loop, listener.fileno)
        assert listener.fileno not in self._poll_handles, "file descriptor was already registered"
        self._poll_handles[listener.fileno] = handle
        events = pyuv.UV_READABLE if listener.evtype == READ else pyuv.UV_WRITABLE
        cb = functools.partial(listener.cb, listener)
        handle.start(events, cb)

    def _remove_poll_handle(self, listener):
        handle = self._poll_handles.pop(listener.fileno, None)
        if handle is not None:
            handle.close()

