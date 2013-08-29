#
# This file is part of Evergreen. See the NOTICE for more information.
#

import pyuv

import evergreen
from evergreen.core.utils import Result
from evergreen.event import Event
from evergreen.io import errno
from evergreen.log import log

__all__ = ['UDPEndpoint', 'UDPError']


UDPError = pyuv.error.UDPError


class UDPEndpoint(object):

    def __init__(self):
        loop = evergreen.current.loop
        self._handle = pyuv.UDP(loop._loop)
        self._closed = False
        self._receive_result = Result()
        self._pending_writes = 0
        self._flush_event = Event()
        self._flush_event.set()

    @property
    def sockname(self):
        self._check_closed()
        return self._handle.getsockname()

    def bind(self, addr):
        self._check_closed()
        self._handle.bind(addr)

    def send(self, data, addr):
        self._check_closed()
        self._handle.send(addr, data, self.__send_cb)
        if self._pending_writes == 0:
            self._flush_event.clear()
        self._pending_writes += 1

    def receive(self):
        self._check_closed()
        with self._receive_result:
            self._handle.start_recv(self.__receive_cb)
            return self._receive_result.get()

    def flush(self):
        self._check_closed()
        self._flush_event.wait()

    def close(self):
        if self._closed:
            return
        self._closed = True
        self._handle.close()

    def _check_closed(self):
        if self._closed:
            raise UDPError('endpoint is closed')

    def __send_cb(self, handle, error):
        self._pending_writes -= 1
        if self._pending_writes == 0:
            self._flush_event.set()
        if error is not None:
            log.debug('send failed: %d %s', error, pyuv.errno.strerror(error))
            evergreen.current.loop.call_soon(self.close)

    def __receive_cb(self, handle, addr, flags, data, error):
        self._handle.stop_recv()
        if error is not None:
            self._receive_result.set_exception(UDPError(error, errno.strerror(error)))
        else:
            self._receive_result.set_value((data, addr))

