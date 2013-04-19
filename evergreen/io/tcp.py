#
# This file is part of Evergreen. See the NOTICE for more information.
#

import pyuv

import evergreen
from evergreen.io.stream import BaseStream, StreamError, StreamConnection, StreamServer
from evergreen.io.util import Result

__all__ = ['TCPServer', 'TCPClient', 'TCPConnection', 'TCPError']


class TCPError(StreamError):
    pass


class TCPStream(BaseStream):
    error_class = TCPError

    def __init__(self, handle):
        super(TCPStream, self).__init__()
        self._handle = handle
        self._read_result = Result()

    @property
    def readable(self):
        return self._handle.readable

    @property
    def writable(self):
        return self._handle.writable

    @property
    def sockname(self):
        self._check_closed()
        return self._handle.getsockname()

    @property
    def peername(self):
        self._check_closed()
        return self._handle.getpeername()

    def _read(self, n):
        try:
            self._handle.start_read(self.__read_cb)
        except pyuv.error.TCPError as e:
            self.close()
            raise TCPError(e.args[0], e.args[1])
        try:
            data = self._read_result.wait()
        except TCPError as e:
            self.close()
            raise
        else:
            if not data:
                self.close()
                return
            self._read_buffer.feed(data)
        finally:
            self._read_result.clear()

    def _write(self, data):
        try:
            self._handle.write(data, self.__write_cb)
        except pyuv.error.TCPError as e:
            self.close()
            raise TCPError(e.args[0], e.args[1])

    def _close(self):
        self._handle.shutdown(self.__shutdown_cb)

    def __read_cb(self, handle, data, error):
        self._handle.stop_read()
        if error is not None:
            if error != pyuv.errno.UV_EOF:
                self._read_result.set_exception(TCPError(error, pyuv.errno.strerror(error)))
            else:
                self._read_result.set_result(b'')
        else:
            self._read_result.set_result(data)

    def __write_cb(self, handle, error):
        if error is not None:
            # TODO: save error?
            self.close()

    def __shutdown_cb(self, handle, error):
        self._handle.close()


class TCPClient(TCPStream):

    def __init__(self):
        loop = evergreen.current.loop
        handle = pyuv.TCP(loop._loop)
        super(TCPClient, self).__init__(handle)
        self._connect_result = None

    def connect(self, target, source_address=None):
        if self._connected:
            raise TCPError('already connected')
        # TODO: getaddrinfo
        if source_address:
            try:
                self._handle.bind(source_address)
            except pyuv.error.TCPError as e:
                raise TCPError(e.args[0], e.args[1])
        try:
            self._handle.connect(target, self.__connect_cb)
        except pyuv.error.TCPError as e:
            raise TCPError(e.args[0], e.args[1])
        self._connect_result = Result()
        try:
            self._connect_result.wait()
        except TCPError:
            self.close()
            raise
        else:
            self._set_connected()
        finally:
            self._connect_result = None

    def __connect_cb(self, handle, error):
        if error is not None:
            self._connect_result.set_exception(TCPError(error, pyuv.errno.strerror(error)))
        else:
            self._connect_result.set_result(None)


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
            raise TCPError(e.args[0], e.args[1])

    def _close(self):
        self._handle.close()

    def __listen_cb(self, handle, error):
        if error is not None:
            # TODO: what can we do?
            self.close()
            return
        tcp_handle = pyuv.TCP(self._handle.loop)
        try:
            self._handle.accept(tcp_handle)
        except pyuv.error.TCPError:
            # TODO: what can we do?
            tcp_handle.close()
        else:
            conn = self.connection_class(tcp_handle)
            conn._set_accepted(self)
            self.handle_connection(conn)

