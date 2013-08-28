#
# This file is part of Evergreen. See the NOTICE for more information.
#

import pyuv

import evergreen
from evergreen.core.utils import Result
from evergreen.io import errno

__all__ = ['UDPEndpoint', 'UDPError']


UDPError = pyuv.error.UDPError


class UDPEndpoint(object):

    def __init__(self):
        loop = evergreen.current.loop
        self._handle = pyuv.UDP(loop._loop)
        self._closed = False
        self._send_result = Result()
        self._receive_result = Result()

    @property
    def sockname(self):
        self._check_closed()
        return self._handle.getsockname()

    def bind(self, addr):
        self._check_closed()
        self._handle.bind(addr)

    def send(self, data, addr):
        self._check_closed()
        with self._send_result:
            self._handle.send(addr, data, self.__send_cb)
            self._send_result.get()

    def receive(self):
        self._check_closed()
        with self._receive_result:
            self._handle.start_recv(self.__receive_cb)
            return self._receive_result.get()

    def close(self):
        if self._closed:
            return
        self._closed = True
        self._handle.close()

    def _check_closed(self):
        if self._closed:
            raise UDPError('endpoint is closed')

    def __send_cb(self, handle, error):
        if error is not None:
            self._send_result.set_exception(UDPError(error, errno.strerror(error)))
        else:
            self._send_result.set_value(None)

    def __receive_cb(self, handle, addr, flags, data, error):
        self._handle.stop_recv()
        if error is not None:
            self._receive_result.set_exception(UDPError(error, errno.strerror(error)))
        else:
            self._receive_result.set_value((data, addr))

