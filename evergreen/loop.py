#
# This file is part of Evergreen. See the NOTICE for more information.
#

import os
import pyuv
import sys
import threading
import traceback

try:
    import signal
except ImportError:
    signal= None

from collections import deque

from evergreen._socketpair import SocketPair
from evergreen._tasklet import tasklet, get_current, TaskletExit
from evergreen._threadpool import ThreadPool

__all__ = ['EventLoop']


_tls = threading.local()


def _noop(*args, **kwargs):
    pass


def get_loop():
    """Get the current event loop singleton object.
    """
    try:
        return _tls.loop
    except AttributeError:
        # create loop only for main thread
        if threading.current_thread().name == 'MainThread':
            _tls.loop = EventLoop()
            return _tls.loop
        raise RuntimeError('there is no event loop created in the current thread')


class Handler(object):
    __slots__ = ('_callback', '_args', '_kwargs', '_cancelled')

    def __init__(self, callback, args=(), kwargs={}):
        self._callback = callback
        self._args = args
        self._kwargs = kwargs
        self._cancelled = False

    @property
    def cancelled(self):
        return self._cancelled

    def cancel(self):
        self._cancelled = True

    def __call__(self):
        if not self._cancelled:
            self._callback(*self._args, **self._kwargs)

    def __repr__(self):
        res = '{}({}, {}, {})'.format(self.__class__.__name__, self._callback, self._args, self._kwargs)
        if self._cancelled:
            res += ' <cancelled>'
        return res


class Timer(Handler):
    __slots__ = ('_timer_h')

    def __init__(self, callback, args=(), kwargs={}, timer=None):
        assert timer is not None
        super(Timer, self).__init__(callback, args, kwargs)
        self._timer_h = timer

    def cancel(self):
        super(Timer, self).cancel()
        if self._timer_h and not self._timer_h.closed:
            loop = self._timer_h.loop.event_loop
            self._timer_h.close()
            loop._timers.remove(self._timer_h)
        self._timer_h = None


class SignalHandler(Handler):
    __slots__ = ('_signal_h')

    def __init__(self, callback, args=(), kwargs={}, signal_h=None):
        assert signal_h is not None
        super(SignalHandler, self).__init__(callback, args, kwargs)
        self._signal_h = signal_h

    def cancel(self):
        super(SignalHandler, self).cancel()
        if self._signal_h and not self._signal_h.closed:
            loop = self._signal_h.loop.event_loop
            self._signal_h.close()
            loop._signals[self._signal_h.signum].discard(self._signal_h)
        self._signal_h = None


class Ticker(pyuv.Idle):
    def tick(self, *args, **kwargs):
        if not self.active:
            self.start(_noop)


class EventLoop(object):

    def __init__(self):
        global _tls
        if getattr(_tls, 'loop', None) is not None:
            raise RuntimeError('cannot instantiate more than one event loop per thread')
        _tls.loop = self
        self._loop = pyuv.Loop()
        self._loop.excepthook = self._handle_error
        self._loop.event_loop = self
        self._threadpool = ThreadPool(self)
        self.tasklet = tasklet(self._run_loop)

        self._started = False
        self._running = False

        self._fd_map = dict()
        self._signals = dict()
        self._timers = set()
        self._ready = deque()

        self._ready_processor = pyuv.Check(self._loop)
        self._ready_processor.start(self._process_ready)
        self._ready_processor.unref()

        self._ticker = Ticker(self._loop)

        self._waker = pyuv.Async(self._loop, self._ticker.tick)
        self._waker.unref()

        self._install_signal_checker()

    @property
    def running(self):
        return self._running

    def call_soon(self, callback, *args, **kw):
        handler = Handler(callback, args, kw)
        self._ready.append(handler)
        self._ticker.tick()
        return handler

    def call_from_thread(self, callback, *args, **kw):
        handler = Handler(callback, args, kw)
        self._ready.append(handler)
        self._waker.send()
        return handler

    def call_later(self, delay, callback, *args, **kw):
        if delay <= 0:
            return self.call_soon(callback, *args, **kw)
        timer = pyuv.Timer(self._loop)
        handler = Timer(callback, args, kw, timer)
        timer.handler = handler
        timer.start(self._timer_cb, delay, 0)
        self._timers.add(timer)
        return handler

    def call_repeatedly(self, interval, callback, *args, **kw):
        if interval <= 0:
            raise ValueError('invalid interval specified: {}'.format(interval))
        timer = pyuv.Timer(self._loop)
        handler = Timer(callback, args, kw, timer)
        timer.handler = handler
        timer.start(self._timer_cb, interval, interval)
        self._timers.add(timer)
        return handler

    def add_reader(self, fd, callback, *args, **kw):
        handler = Handler(callback, args, kw)
        try:
            poll_h = self._fd_map[fd]
        except KeyError:
            poll_h = self._create_poll_handle(fd)
            self._fd_map[fd] = poll_h
        else:
            if poll_h.read_handler:
                raise RuntimeError('another reader is already registered for fd {}'.format(fd))
            poll_h.stop()

        poll_h.pevents |= pyuv.UV_READABLE
        poll_h.read_handler = handler
        poll_h.start(poll_h.pevents, self._poll_cb)

        return handler

    def remove_reader(self, fd):
        try:
            poll_h = self._fd_map[fd]
        except KeyError:
            return False
        else:
            poll_h.stop()
            poll_h.pevents &= ~pyuv.UV_READABLE
            poll_h.read_handler = None
            if poll_h.pevents == 0:
                poll_h.close()
                del self._fd_map[fd]
            else:
                poll_h.start(poll_h.pevents, self._poll_cb)
            return True

    def add_writer(self, fd, callback, *args, **kw):
        handler = Handler(callback, args, kw)
        try:
            poll_h = self._fd_map[fd]
        except KeyError:
            poll_h = self._create_poll_handle(fd)
            self._fd_map[fd] = poll_h
        else:
            if poll_h.write_handler:
                raise RuntimeError('another writer is already registered for fd {}'.format(fd))
            poll_h.stop()

        poll_h.pevents |= pyuv.UV_WRITABLE
        poll_h.write_handler = handler
        poll_h.start(poll_h.pevents, self._poll_cb)

        return handler

    def remove_writer(self, fd):
        try:
            poll_h = self._fd_map[fd]
        except KeyError:
            return False
        else:
            poll_h.stop()
            poll_h.pevents &= ~pyuv.UV_WRITABLE
            poll_h.write_handler = None
            if poll_h.pevents == 0:
                poll_h.close()
                del self._fd_map[fd]
            else:
                poll_h.start(poll_h.pevents, self._poll_cb)
            return True

    def add_signal_handler(self, sig, callback, *args, **kwargs):
        self._validate_signal(sig)
        signal_h = pyuv.Signal(self._loop)
        handler = SignalHandler(callback, args, kwargs, signal_h)
        signal_h.handler = handler
        signal_h.signum = sig
        try:
            signal_h.start(self._signal_cb, sig)
            signal_h.unref()
        except Exception as e:
            signal_h.close()
            raise RuntimeError(str(e))
        else:
            self._signals.setdefault(sig, set()).add(signal_h)
        return handler

    def remove_signal_handler(self, sig):
        self._validate_signal(sig)
        try:
            handles = self._signals.pop(sig)
        except KeyError:
            return False
        for signal_h in handles:
            del signal_h.handler
            signal_h.close()
        return True

    def switch(self):
        if not self._started:
            self._run(forever=False)
            return
        current = get_current()
        assert current is not self.tasklet, 'Cannot switch to MAIN from MAIN'
        try:
            if self.tasklet.parent is not current:
                current.parent = self.tasklet
        except ValueError:
            pass  # gets raised if there is a tasklet parent cycle
        return self.tasklet.switch()

    def run(self):
        self._run(forever=False)

    def run_forever(self):
        self._run(forever=True)

    def stop(self):
        if not self._started:
            raise RuntimeError('event loop has not been started yet')
        if self._loop:
            self._loop.stop()

    def destroy(self):
        if self._running:
            raise RuntimeError('destroy() cannot be called while the loop is running')

        try:
            loop = _tls.loop
        except AttributeError:
            return
        else:
            if loop is not self:
                raise RuntimeError('destroy() can only be called from the same thread were the event loop was created')
            del _tls.loop, loop

        self._uninstall_signal_checker()

        self._cleanup_loop()
        self._loop.event_loop = None
        self._loop.excepthook = None
        self._loop = None
        self._threadpool = None

        self._ready_processor = None
        self._ticker = None
        self._waker = None

        self._fd_map.clear()
        self._signals.clear()
        self._timers.clear()
        self._ready.clear()

    # internal

    def _handle_error(self, typ, value, tb):
        if not issubclass(typ, (TaskletExit, SystemExit)):
            traceback.print_exception(typ, value, tb)
        if issubclass(typ, (KeyboardInterrupt, SystemExit, SystemError)):
            current = get_current()
            assert current is self.tasklet
            self.tasklet.parent.throw(typ, value)

    def _run(self, forever):
        current = get_current()
        if current is not self.tasklet.parent:
            raise RuntimeError('run() can only be called from MAIN tasklet')
        if self.tasklet.dead:
            raise RuntimeError('event loop has already ended')
        if self._started:
            raise RuntimeError('event loop was already started')
        self._started = True
        self._running = True
        try:
            self.tasklet.switch(forever=forever)
        finally:
            self._running = False

    def _run_loop(self, forever=False):
        if forever:
            handler = self.call_repeatedly(24*3600, lambda: None)
        try:
            self._loop.run(pyuv.UV_RUN_DEFAULT)
        finally:
            if forever:
                handler.cancel()

    def _cleanup_loop(self):
        def cb(handle):
            if not handle.closed:
                handle.close()
        self._loop.walk(cb)
        # All handles are now closed, run will not block
        self._loop.run(pyuv.UV_RUN_NOWAIT)

    def _create_poll_handle(self, fd):
        poll_h = pyuv.Poll(self._loop, fd)
        poll_h.pevents = 0
        poll_h.read_handler = None
        poll_h.write_handler = None
        return poll_h

    def _process_ready(self, handle):
        # Run all queued callbacks
        ntodo = len(self._ready)
        for x in range(ntodo):
            handler = self._ready.popleft()
            # loop.excepthook takes care of exception handling
            handler()
        if not self._ready:
            self._ticker.stop()

    def _timer_cb(self, timer):
        assert not timer.handler.cancelled
        self._ready.append(timer.handler)
        if not timer.repeat:
            timer.close()
            self._timers.remove(timer)
            del timer.handler

    def _signal_cb(self, signal_h, signum):
        self._ready.append(signal_h.handler)

    def _poll_cb(self, poll_h, events, error):
        fd = poll_h.fileno()
        if error is not None:
            # An error happened, signal both readability and writability and
            # let the error propagate
            if poll_h.read_handler is not None:
                if poll_h.read_handler.cancelled:
                    self.remove_reader(fd)
                else:
                    self._ready.append(poll_h.read_handler)
            if poll_h.write_handler is not None:
                if poll_h.write_handler.cancelled:
                    self.remove_writer(fd)
                else:
                    self._ready.append(poll_h.write_handler)
            return

        old_events = poll_h.pevents
        modified = False

        if events & pyuv.UV_READABLE:
            if poll_h.read_handler is not None:
                if poll_h.read_handler.cancelled:
                    self.remove_reader(fd)
                    modified = True
                else:
                    self._ready.append(poll_h.read_handler)
            else:
                poll_h.pevents &= ~pyuv.UV_READABLE
        if events & pyuv.UV_WRITABLE:
            if poll_h.write_handler is not None:
                if poll_h.write_handler.cancelled:
                    self.remove_writer(fd)
                    modified = True
                else:
                    self._ready.append(poll_h.write_handler)
            else:
                poll_h.pevents &= ~pyuv.UV_WRITABLE

        if not modified and old_events != poll_h.pevents:
            # Rearm the handle
            poll_h.stop()
            poll_h.start(poll_h.pevents, self._poll_cb)

    def _install_signal_checker(self):
        self._socketpair = SocketPair()
        self._signal_checker = None
        if hasattr(signal, 'set_wakeup_fd') and os.name == 'posix':
            try:
                old_wakeup_fd = signal.set_wakeup_fd(self._socketpair.writer_fileno())
                if old_wakeup_fd != -1:
                    # Already set, restore it
                    signal.set_wakeup_fd(old_wakeup_fd)
                    self._socketpair.close()
                    self._socketpair = None
                else:
                    self._signal_checker = pyuv.util.SignalChecker(self._loop, self._socketpair.reader_fileno())
                    self._signal_checker.start()
                    self._signal_checker.unref()
            except ValueError:
                self._socketpair.close()
                self._socketpair = None

    def _uninstall_signal_checker(self):
        if self._signal_checker:
            self._signal_checker.close()
            self._signal_checker = None
        if self._socketpair:
            self._socketpair.close()
            self._socketpair = None

    def _validate_signal(self, sig):
        if not isinstance(sig, int):
            raise TypeError('sig must be an int, not {!r}'.format(sig))
        if signal is None:
            raise RuntimeError('Signals are not supported')
        if not (1 <= sig < signal.NSIG):
            raise ValueError('sig {} out of range(1, {})'.format(sig, signal.NSIG))
        if sys.platform == 'win32':
            raise RuntimeError('Signals are not really supported on Windows')

