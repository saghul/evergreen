#
# This file is part of Evergreen. See the NOTICE for more information.
#

import pyuv

import evergreen
from evergreen.io.stream import BaseStream, StreamError, StreamConnection, StreamServer
from evergreen.io.util import Result, convert_errno
from evergreen.lib import socket
from evergreen.log import log

__all__ = ['TCPServer', 'TCPClient', 'TCPConnection', 'TCPError']


class TCPError(StreamError):
    pass


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

    def _read(self, n):
        read_result = Result()
        def cb(handle, data, error):
            self._handle.stop_read()
            if error is not None:
                if error != pyuv.errno.UV_EOF:
                    read_result.set_exception(TCPError(error, pyuv.errno.strerror(error)))
                else:
                    read_result.set_result(b'')
            else:
                read_result.set_result(data)

        try:
            self._handle.start_read(cb)
        except pyuv.error.TCPError as e:
            self.close()
            raise TCPError(convert_errno(e.args[0]), e.args[1])
        try:
            data = read_result.wait()
        except TCPError as e:
            self.close()
            raise
        else:
            if not data:
                self.close()
                return
            self._read_buffer.feed(data)

    def _write(self, data):
        try:
            self._handle.write(data, self.__write_cb)
        except pyuv.error.TCPError as e:
            self.close()
            raise TCPError(convert_errno(e.args[0]), e.args[1])

    def _close(self):
        self._handle.shutdown(self.__shutdown_cb)

    def __write_cb(self, handle, error):
        if error is not None:
            log.debug('write failed: %d %s', convert_errno(error), pyuv.errno.strerror(error))
            evergreen.current.loop.call_soon(self.close)

    def __shutdown_cb(self, handle, error):
        self._handle.close()


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

        connect_result = Result()
        def cb(handle, error):
            if error is not None:
                connect_result.set_exception(TCPError(convert_errno(error), pyuv.errno.strerror(error)))
            else:
                connect_result.set_result(None)

        err = None
        loop = self._handle.loop
        for item in r:
            addr = item[-1]
            if '%' in addr[0]:
                # Skip addresses such as 'fe80::1%lo0'
                # TODO: handle this properly
                continue
            handle = pyuv.TCP(loop)
            try:
                if source_address:
                    handle.bind(source_address)
                handle.connect(addr, cb)
            except pyuv.error.TCPError as e:
                err = TCPError(convert_errno(e.args[0]), e.args[1])
                handle.close()
                continue
            try:
                connect_result.wait()
            except TCPError as e:
                err = e
                handle.close()
                connect_result.clear()
                continue
            else:
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
        try:
            self._handle.listen(self.__listen_cb, backlog)
        except pyuv.error.TCPError as e:
            raise TCPError(convert_errno(e.args[0]), e.args[1])

    def _close(self):
        self._handle.close()

    def __listen_cb(self, handle, error):
        if error is not None:
            log.debug('listen failed: %d %s', convert_errno(error), pyuv.errno.strerror(error))
            return
        tcp_handle = pyuv.TCP(self._handle.loop)
        try:
            self._handle.accept(tcp_handle)
        except pyuv.error.TCPError:
            log.debug('accept failed: %d %s', convert_errno(e.args[0]), pyuv.errno.strerror(e.args[1]))
            tcp_handle.close()
        else:
            conn = self.connection_class(tcp_handle)
            conn._set_accepted(self)
            self.handle_connection(conn)

