#
# This file is part of Evergreen. See the NOTICE for more information.
#

import pyuv

import evergreen
from evergreen.core.utils import Result
from evergreen.io import errno
from evergreen.io.stream import BaseStream, StreamConnection, StreamServer
from evergreen.lib import socket
from evergreen.log import log

__all__ = ['TCPServer', 'TCPClient', 'TCPConnection', 'TCPError']


TCPError = pyuv.error.TCPError


class TCPStream(BaseStream):
    error_cls = TCPError

    def __init__(self, handle):
        super(TCPStream, self).__init__()
        self._handle = handle

    @property
    def sockname(self):
        self._check_closed()
        return self._handle.getsockname()

    @property
    def peername(self):
        self._check_closed()
        return self._handle.getpeername()


class TCPClient(TCPStream):

    def __init__(self):
        loop = evergreen.current.loop
        handle = pyuv.TCP(loop._loop)
        super(TCPClient, self).__init__(handle)
        self._connect_result = Result()

    def connect(self, target, source_address=None):
        if self._connected:
            raise TCPError('already connected')
        host, port = target
        try:
            r = socket.getaddrinfo(host, port, socket.AF_UNSPEC, socket.SOCK_STREAM)
        except socket.error as e:
            raise TCPError(e)
        if not r:
            raise TCPError('getaddrinfo returned no result')

        err = None
        loop = self._handle.loop
        for item in r:
            with self._connect_result:
                addr = item[-1]
                idx = addr[0].find('%')
                if idx != -1:
                    host, rest = addr[0], addr[1:]
                    addr = (host[:idx],) + rest
                handle = pyuv.TCP(loop)
                try:
                    if source_address:
                        handle.bind(source_address)
                    handle.connect(addr, self.__connect_cb)
                except TCPError as e:
                    err = e
                    handle.close()
                    continue
                try:
                    self._connect_result.get()
                except TCPError as e:
                    err = e
                    handle.close()
                    continue
                else:
                    self._handle.close()
                    self._handle = handle
                    break
        if err is not None:
            raise err
        self._set_connected()

    def __connect_cb(self, handle, error):
        if error is not None:
            self._connect_result.set_exception(TCPError(error, errno.strerror(error)))
        else:
            self._connect_result.set_value(None)


class TCPConnection(TCPStream, StreamConnection):
    pass


class TCPServer(StreamServer):
    connection_cls = TCPConnection
    error_cls = TCPError

    def __init__(self):
        super(TCPServer, self).__init__()
        loop = evergreen.current.loop
        self._handle = pyuv.TCP(loop._loop)

    @property
    def sockname(self):
        self._check_closed()
        return self._handle.getsockname()

    def _bind(self, address):
        self._handle.bind(address)

    def _serve(self, backlog):
        self._handle.listen(self.__listen_cb, backlog)

    def _close(self):
        self._handle.close()

    def __listen_cb(self, handle, error):
        if error is not None:
            log.debug('listen failed: %d %s', error, errno.strerror(error))
            return
        tcp_handle = pyuv.TCP(self._handle.loop)
        try:
            self._handle.accept(tcp_handle)
        except TCPError as e:
            log.debug('accept failed: %d %s', e.args[0], e.args[1])
            tcp_handle.close()
        else:
            conn = self.connection_cls(tcp_handle)
            conn._set_accepted(self)
            self.handle_connection(conn)

