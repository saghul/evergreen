# -*- coding: utf-8 -
#
# This file is part of flubber. See the NOTICE for more information.

import os
import pyuv
import signal
import traceback

from collections import deque

from flubber import patcher
from flubber.threadpool import ThreadPool
from flubber._socketpair import SocketPair
from flubber._tasklet import tasklet, get_current, TaskletExit


__all__ = ['get_hub', 'Hub']


threading = patcher.original('threading')
_tls = threading.local()


def get_hub():
    """Get the current event hub singleton object.
    """
    try:
        return _tls.hub
    except AttributeError:
        raise RuntimeError('there is no hub created in the current thread')


class Handler(object):

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
        self._callback(*self._args, **self._kwargs)

    def __repr__(self):
        res = '{}({}, {}, {})'.format(self.__class__.__name__, self._callback, self._args, self._kwargs)
        if self._cancelled:
            res += ' <cancelled>'
        return res


class Hub(object):

    def __init__(self):
        global _tls
        if getattr(_tls, 'hub', None) is not None:
            raise RuntimeError('cannot instantiate more than one Hub per thread')
        _tls.hub = self
        self.tasklet = tasklet(self._run_loop)
        self.loop = pyuv.Loop()
        self.loop.excepthook = self._handle_error
        self.threadpool = ThreadPool(self)

        self._started = False

        self._fd_map = dict()
        self._timers = set()
        self._ready = deque()

        self._waker = pyuv.Async(self.loop, lambda x: None)
        self._waker.unref()

        self._ready_processor = pyuv.Check(self.loop)
        self._ready_processor.start(self._process_ready)

        self._install_signal_checker()

    def call_soon(self, callback, *args, **kw):
        handler = Handler(callback, args, kw)
        self._ready.append(handler)
        return handler

    def call_from_thread(self, callback, *args, **kw):
        handler = self.call_soon(callback, *args, **kw)
        self._waker.send()
        return handler

    def call_later(self, delay, callback, *args, **kw):
        if delay <= 0:
            return self.call_soon(callback, *args, **kw)
        handler = Handler(callback, args, kw)
        timer = pyuv.Timer(self.loop)
        timer.handler = handler
        timer.start(self._timer_cb, delay, 0)
        self._timers.add(timer)
        return handler

    def call_repeatedly(self, interval, callback, *args, **kw):
        if interval <= 0:
            raise ValueError('invalid interval specified: {}'.format(interval))
        handler = Handler(callback, args, kw)
        timer = pyuv.Timer(self.loop)
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

    def switch(self):
        if not self._started:
            raise RuntimeError('Hub was not started, run() needs to be called first')
        current = get_current()
        switch_out = getattr(current, 'switch_out', None)
        if switch_out is not None:
            switch_out()
        try:
            if self.tasklet.parent is not current:
                current.parent = self.tasklet
        except ValueError:
            pass  # gets raised if there is a tasklet parent cycle
        return self.tasklet.switch()

    def switch_out(self):
        raise RuntimeError('Cannot switch to MAIN from MAIN')

    def run(self):
        current = get_current()
        if current is not self.tasklet.parent:
            raise RuntimeError('run() can only be called from MAIN tasklet')
        if self.tasklet.dead:
            raise RuntimeError('hub has already ended')
        if self._started:
            raise RuntimeError('hub was already started')
        self._started = True
        self.tasklet.switch()

    def destroy(self):
        global _tls
        try:
            hub = _tls.hub
        except AttributeError:
            raise RuntimeError('hub is already destroyed')
        else:
            if hub is not self:
                raise RuntimeError('destroy() can only be called from the same thread were the hub was created')
            del _tls.hub, hub

        self._uninstall_signal_checker()

        self._cleanup_loop()
        self.loop.excepthook = None
        self.loop = None
        self.threadpool = None

        self._waker = None
        self._ready_processor = None

        self._fd_map.clear()
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

    def _run_loop(self):
        run_once = self._run_once
        while run_once():
            pass

    def _run_once(self):
        # Check timers
        for timer in [timer for timer in self._timers if timer.handler.cancelled]:
            timer.close()
            self._timers.remove(timer)
            del timer.handler

        # Make sure the loop iterates but doesn't block for i/o if there are pending callbacks
        if self._ready:
            self._ready_processor.ref()
            mode = pyuv.UV_RUN_NOWAIT
        else:
            self._ready_processor.unref()
            mode = pyuv.UV_RUN_ONCE

        return self.loop.run(mode)

    def _cleanup_loop(self):
        def cb(handle):
            if not handle.closed:
                handle.close()
        self.loop.walk(cb)
        # All handles are now closed, run will not block
        self.loop.run(pyuv.UV_RUN_NOWAIT)

    def _create_poll_handle(self, fd):
        poll_h = pyuv.Poll(self.loop, fd)
        poll_h.pevents = 0
        poll_h.read_handler = None
        poll_h.write_handler = None
        return poll_h

    def _process_ready(self, handle):
        ntodo = len(self._ready)
        for x in xrange(ntodo):
            handler = self._ready.popleft()
            if not handler.cancelled:
                # loop.excepthook takes care of exception handling
                handler()
        if not self._ready:
            self._ready_processor.unref()
        else:
            self._ready_processor.ref()

    def _timer_cb(self, timer):
        if timer.handler.cancelled:
            timer.close()
            self._timers.remove(timer)
            del timer.handler
            return
        self._ready.append(timer.handler)
        if not timer.repeat:
            timer.close()
            self._timers.remove(timer)
            del timer.handler

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
        if hasattr(signal, 'set_wakeup_fd') and os.name == 'posix':
            try:
                old_wakeup_fd = signal.set_wakeup_fd(self._socketpair.writer_fileno())
                if old_wakeup_fd != -1:
                    # Already set, restore it
                    signal.set_wakeup_fd(old_wakeup_fd)
                    self._socketpair.close()
                    self._socketpair = None
                else:
                    self._signal_checker = pyuv.util.SignalChecker(self.loop, self._socketpair.reader_fileno())
                    self._signal_checker.start()
                    self._signal_checker.unref()
            except ValueError:
                self._socketpair.close()
                self._socketpair = None

    def _uninstall_signal_checker(self):
        if self._socketpair:
            self._signal_checker.close()
            self._signal_checker = None
            self._socketpair.close()
            self._socketpair = None

