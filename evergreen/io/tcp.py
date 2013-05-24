#
# This file is part of Evergreen. See the NOTICE for more information.
#

import pyuv

import evergreen
from evergreen.futures import Future
from evergreen.io.stream import BaseStream, StreamConnection, StreamServer
from evergreen.lib import socket
from evergreen.log import log

__all__ = ['TCPServer', 'TCPClient', 'TCPConnection', 'TCPError']


TCPError = pyuv.error.TCPError


class TCPStream(BaseStream):
    error_class = TCPError

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

        def cb(handle, error):
            if error is not None:
                handle.connect_result.set_exception(TCPError(error, pyuv.errno.strerror(error)))
            else:
                handle.connect_result.set_result(None)

        err = None
        loop = self._handle.loop
        for item in r:
            connect_result = Future()
            addr = item[-1]
            idx = addr[0].find('%')
            if idx != -1:
                host, rest = addr[0], addr[1:]
                addr = (host[:idx],) + rest
            handle = pyuv.TCP(loop)
            handle.connect_result = connect_result
            try:
                if source_address:
                    handle.bind(source_address)
                handle.connect(addr, cb)
            except TCPError as e:
                err = e
                handle.close()
                continue
            try:
                connect_result.get()
            except TCPError as e:
                err = e
                handle.close()
                del handle.connect_result
                continue
            else:
                del handle.connect_result
                self._handle.close()
                self._handle = handle
                break
        if err is not None:
            raise err
        self._set_connected()


class TCPConnection(TCPStream, StreamConnection):
    pass


class TCPServer(StreamServer):
    connection_class = TCPConnection
    error_class = TCPError

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
            log.debug('listen failed: %d %s', error, pyuv.errno.strerror(error))
            return
        tcp_handle = pyuv.TCP(self._handle.loop)
        try:
            self._handle.accept(tcp_handle)
        except TCPError as e:
            log.debug('accept failed: %d %s', e.args[0], pyuv.errno.strerror(e.args[1]))
            tcp_handle.close()
        else:
            conn = self.connection_class(tcp_handle)
            conn._set_accepted(self)
            self.handle_connection(conn)

