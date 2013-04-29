#
# This file is part of Evergreen. See the NOTICE for more information.
#

import pyuv

import evergreen
from evergreen.io.stream import BaseStream, StreamError, StreamConnection, StreamServer
from evergreen.io.util import Result, convert_errno

__all__ = ['PipeServer', 'PipeClient', 'PipeConnection', 'PipeError']


class PipeError(StreamError):
    pass


class PipeStream(BaseStream):
    error_class = PipeError

    def __init__(self, handle):
        super(PipeStream, self).__init__()
        self._handle = handle

    @property
    def readable(self):
        return self._handle.readable

    @property
    def writable(self):
        return self._handle.writable

    def _read(self, n):
        read_result = Result()
        def cb(handle, data, error):
            self._handle.stop_read()
            if error is not None:
                if error != pyuv.errno.UV_EOF:
                    read_result.set_exception(PipeError(convert_errno(error), pyuv.errno.strerror(error)))
                else:
                    read_result.set_result(b'')
            else:
                read_result.set_result(data)

        try:
            self._handle.start_read(cb)
        except pyuv.error.PipeError as e:
            self.close()
            raise PipeError(convert_errno(e.args[0]), e.args[1])
        try:
            data = read_result.wait()
        except PipeError as e:
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
        except pyuv.error.PipeError as e:
            self.close()
            raise PipeError(convert_errno(e.args[0]), e.args[1])

    def _close(self):
        self._handle.shutdown(self.__shutdown_cb)

    def __write_cb(self, handle, error):
        if error is not None:
            # TODO: save error?
            self.close()

    def __shutdown_cb(self, handle, error):
        self._handle.close()


class PipeConnection(PipeStream, StreamConnection):
    pass


class PipeClient(PipeStream):

    def __init__(self):
        loop = evergreen.current.loop
        handle = pyuv.Pipe(loop._loop)
        super(PipeClient, self).__init__(handle)

    def connect(self, target):
        if self._connected:
            raise PipeError('already connected')

        connect_result = Result()
        def cb(handle, error):
            if error is not None:
                connect_result.set_exception(PipeError(convert_errno(error), pyuv.errno.strerror(error)))
            else:
                connect_result.set_result(None)

        try:
            self._handle.connect(target, cb)
        except pyuv.error.PipeError as e:
            raise PipeError(convert_errno(e.args[0]), e.args[1])
        try:
            connect_result.wait()
        except PipeError:
            self.close()
            raise
        else:
            self._set_connected()


class PipeServer(StreamServer):
    connection_class = PipeConnection
    error_class = PipeError

    def __init__(self):
        super(PipeServer, self).__init__()
        loop = evergreen.current.loop
        self._handle = pyuv.Pipe(loop._loop)
        self._name = None

    @property
    def pipename(self):
        self._check_closed()
        return self._name

    def _bind(self, name):
        self._handle.bind(name)
        self._name = name

    def _serve(self, backlog):
        try:
            self._handle.listen(self.__listen_cb, backlog)
        except pyuv.error.PipeError as e:
            raise PipeError(convert_errno(e.args[0]), e.args[1])

    def _close(self):
        self._handle.close()

    def __listen_cb(self, handle, error):
        if error is not None:
            # TODO: what can we do?
            self.close()
            return
        pipe_handle = pyuv.Pipe(self._handle.loop)
        try:
            self._handle.accept(pipe_handle)
        except pyuv.error.PipeError:
            # TODO: what can we do?
            pipe_handle.close()
        else:
            conn = self.connection_class(pipe_handle)
            conn._set_accepted(self)
            self.handle_connection(conn)

