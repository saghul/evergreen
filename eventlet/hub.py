
import os
import pyuv
import sys
import traceback

from collections import deque
from functools import partial

from eventlet.support import greenlets as greenlet, clear_sys_exc_info
from eventlet.threadpool import ThreadPool
from eventlet import patcher
time = patcher.original('time')
threading = patcher.original('threading')
_threadlocal = threading.local()

__all__ = ["get_hub", "trampoline"]


SYSTEM_EXCEPTIONS = (KeyboardInterrupt, SystemExit)
READ  = 'READ'
WRITE = 'WRITE'


def get_hub():
    """Get the current event hub singleton object.
    """
    try:
        hub = _threadlocal.hub
    except AttributeError:
        hub = _threadlocal.hub = Hub()
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
    """
    hub = get_hub()
    return hub.wait_fd(fd, read, write, timeout, timeout_exc)


class FdListener(object):
    def __init__(self, evtype, fileno, cb):
        assert (evtype is READ or evtype is WRITE)
        self.evtype = evtype
        self.fileno = fileno
        self.cb = cb
    def __repr__(self):
        return "%s(%r, %r, %r)" % (type(self).__name__, self.evtype, self.fileno, self.cb)
    __str__ = __repr__


noop = FdListener(READ, 0, lambda x: None)

# in debug mode, track the call site that created the listener
class DebugListener(FdListener):
    def __init__(self, evtype, fileno, cb):
        self.where_called = traceback.format_stack()
        self.greenlet = greenlet.getcurrent()
        super(DebugListener, self).__init__(evtype, fileno, cb)
    def __repr__(self):
        return "DebugListener(%r, %r, %r, %r)\n%sEndDebugFdListener" % (
            self.evtype,
            self.fileno,
            self.cb,
            self.greenlet,
            ''.join(self.where_called))
    __str__ = __repr__


class Waker(object):

    def __init__(self, hub):
        self._async = pyuv.Async(hub.loop, lambda x: None)
        self._async.unref()

    def wake(self):
        self._async.send()


class Hub(object):

    def __init__(self):
        self.greenlet = greenlet.greenlet(self.run)
        self.loop = pyuv.Loop()
        self.threadpool = ThreadPool(self)

        self._listeners = {READ:{}, WRITE:{}}
        self._timers = set()
        self._poll_handles = {}
        self._waker = Waker(self)
        self._tick_prepare = pyuv.Prepare(self.loop)
        self._tick_idle = pyuv.Idle(self.loop)
        self._tick_callbacks = deque()

        self.stopping = False
        self.running = False
        self.lclass = FdListener
        self.debug_exceptions = True

    def add(self, evtype, fileno, cb):
        """ Signals an intent to or write a particular file descriptor.

        The *evtype* argument is either the constant READ or WRITE.

        The *fileno* argument is the file number of the file of interest.

        The *cb* argument is the callback which will be called when the file
        is ready for reading/writing.
        """
        listener = self.lclass(evtype, fileno, cb)
        bucket = self._listeners[evtype]
        if fileno in bucket:
            raise RuntimeError("Second simultaneous %s on fileno %s " % (evtype, fileno))
        bucket[fileno] = listener
        self._add_poll_handle(listener)
        return listener

    def remove(self, listener):
        self._remove_poll_handle(listener)
        fileno = listener.fileno
        evtype = listener.evtype
        self._listeners[evtype].pop(fileno, None)

    def remove_descriptor(self, fileno):
        """ Completely remove all listeners for this fileno.  For internal use
        only."""
        listeners = []
        listeners.append(self._listeners[READ].pop(fileno, noop))
        listeners.append(self._listeners[WRITE].pop(fileno, noop))
        for listener in listeners:
            try:
                listener.cb(fileno)
            except Exception:
                self.squelch_generic_exception(sys.exc_info())

    def switch(self):
        cur = greenlet.getcurrent()
        assert cur is not self.greenlet, 'Cannot switch to MAINLOOP from MAINLOOP'
        switch_out = getattr(cur, 'switch_out', None)
        if switch_out is not None:
            try:
                switch_out()
            except:
                self.squelch_generic_exception(sys.exc_info())
        if self.greenlet.dead:
            self.greenlet = greenlet.greenlet(self.run)
        try:
            if self.greenlet.parent is not cur:
                cur.parent = self.greenlet
        except ValueError:
            pass  # gets raised if there is a greenlet parent cycle
        clear_sys_exc_info()
        return self.greenlet.switch()

    def squelch_exception(self, fileno, exc_info):
        traceback.print_exception(*exc_info)
        sys.stderr.write("Removing descriptor: %r\n" % (fileno,))
        sys.stderr.flush()
        try:
            self.remove_descriptor(fileno)
        except Exception, e:
            sys.stderr.write("Exception while removing descriptor! %r\n" % (e,))
            sys.stderr.flush()

    def next_tick(self, func, *args, **kw):
        self._tick_callbacks.append(partial(func, *args, **kw))
        if not self._tick_prepare.active:
            self._tick_prepare.start(self._tick_cb)
            self._tick_idle.start(lambda handle: handle.stop())

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
                try:
                    self.loop.run_once()
                except SYSTEM_EXCEPTIONS:
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
            assert self.greenlet is not greenlet.getcurrent(), "Can't abort with wait from inside the hub's greenlet."
            # wakeup loop, in case it was busy polling
            self._waker.wake()
            self.switch()

    def squelch_generic_exception(self, exc_info):
        if self.debug_exceptions:
            traceback.print_exception(*exc_info)
            sys.stderr.flush()
            clear_sys_exc_info()

    def squelch_timer_exception(self, timer, exc_info):
        if self.debug_exceptions:
            traceback.print_exception(*exc_info)
            sys.stderr.flush()
            clear_sys_exc_info()

    def schedule_call_local(self, seconds, cb, *args, **kw):
        """Schedule a callable to be called after 'seconds' seconds have
        elapsed. Cancel the timer if greenlet has exited.
            seconds: The number of seconds to wait.
            cb: The callable to call after the given time.
            *args: Arguments to pass to the callable when called.
            **kw: Keyword arguments to pass to the callable when called.
        """
        current = greenlet.getcurrent()
        if current is self.greenlet:
            return self.schedule_call_global(seconds, cb, *args, **kw)
        timer = LocalTimer(self, seconds, cb, *args, **kw)
        return timer

    def schedule_call_global(self, seconds, cb, *args, **kw):
        """Schedule a callable to be called after 'seconds' seconds have
        elapsed. The timer will NOT be canceled if the current greenlet has
        exited before the timer fires.
            seconds: The number of seconds to wait.
            cb: The callable to call after the given time.
            *args: Arguments to pass to the callable when called.
            **kw: Keyword arguments to pass to the callable when called.
        """
        timer = Timer(self, seconds, cb, *args, **kw)
        return timer

    def wait_fd(self, fd, read=None, write=None, timeout=None, timeout_exc=None):
        from eventlet.timeout import Timeout
        timeout_exc = timeout_exc or Timeout
        t = None
        current = greenlet.getcurrent()
        assert self.greenlet is not current, 'do not call blocking functions from the mainloop'
        assert not (read and write), 'not allowed to trampoline for reading and writing'
        try:
            fileno = fd.fileno()
        except AttributeError:
            fileno = fd
        if timeout is not None:
            t = self.schedule_call_global(timeout, current.throw, timeout_exc)
        try:
            if read:
                listener = self.add(READ, fileno, current.switch)
            elif write:
                listener = self.add(WRITE, fileno, current.switch)
            try:
                return self.switch()
            finally:
                self.remove(listener)
        finally:
            if t is not None:
                t.cancel()

    # for debugging:

    @property
    def readers(self):
        return self._listeners[READ].values()

    @property
    def writers(self):
        return self._listeners[WRITE].values()

    def set_debug_listeners(self, value):
        if value:
            self.lclass = DebugListener
        else:
            self.lclass = FdListener

    # private

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
            try:
                f()
            except SYSTEM_EXCEPTIONS:
                raise
            except:
                self.squelch_generic_exception(sys.exc_info())
                clear_sys_exc_info()

    def _poll_cb(self, listener, handle, error):
        try:
            listener.cb(listener.fileno)
        except SYSTEM_EXCEPTIONS:
            raise
        except:
            self.squelch_exception(listener.fileno, sys.exc_info())
            clear_sys_exc_info()

    def _add_poll_handle(self, listener):
        handle = pyuv.Poll(self.loop, listener.fileno)
        self._poll_handles[listener.fileno] = handle
        events = pyuv.UV_READABLE if listener.evtype == READ else pyuv.UV_WRITABLE
        handle.start(events, partial(listener.cb, listener))

    def _remove_poll_handle(self, listener):
        handle = self._poll_handles.pop(listener.fileno, None)
        if handle is not None:
            handle.close()


class Timer(object):

    def __init__(self, hub, seconds, cb, *args, **kw):
        self.called = False
        self.cb = partial(cb, *args, **kw)
        self._hub = hub
        self._hub._timers.add(self)
        self._timer = pyuv.Timer(hub.loop)
        self._timer.start(self._timer_cb, seconds, 0.0)

    def _timer_cb(self, timer):
        if not self.called:
            self.called = True
            try:
                self.cb()
            except SYSTEM_EXCEPTIONS:
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


class LocalTimer(Timer):

    def __init__(self, hub, seconds, cb, *args, **kw):
        self.greenlet = greenlet.getcurrent()
        super(LocalTimer, self).__init__(hub, seconds, cb, *args, **kw)

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
            except SYSTEM_EXCEPTIONS:
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
        super(LocalTimer, self).cancel()

