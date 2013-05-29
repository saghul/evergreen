#
# This file is part of Evergreen. See the NOTICE for more information.
#

import pyuv

import evergreen
from evergreen.futures import Future
from evergreen.io import errno

__all__ = ['UDPEndpoint', 'UDPError']


UDPError = pyuv.error.UDPError


class UDPEndpoint(object):

    def __init__(self):
        loop = evergreen.current.loop
        self._handle = pyuv.UDP(loop._loop)
        self._closed = False

    @property
    def sockname(self):
        self._check_closed()
        return self._handle.getsockname()

    def bind(self, addr):
        self._check_closed()
        self._handle.bind(addr)

    def send(self, data, addr):
        self._check_closed()
        f = Future()
        def cb(handle, error):
            if error is not None:
                f.set_exception(UDPError(error, errno.strerror(error)))
            else:
                f.set_result(None)
        self._handle.send(addr, data, cb)
        f.get()

    def receive(self):
        self._check_closed()
        f = Future()
        def cb(handle, addr, flags, data, error):
            self._handle.stop_recv()
            if error is not None:
                f.set_exception(UDPError(error, errno.strerror(error)))
            else:
                f.set_result((data, addr))
        self._handle.start_recv(cb)
        return f.get()

    def close(self):
        if self._closed:
            return
        self._closed = True
        self._handle.close()

    def _check_closed(self):
        if self._closed:
            raise UDPError('endpoint is closed')

