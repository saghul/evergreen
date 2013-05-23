#
# This file is part of Evergreen. See the NOTICE for more information.
#

import pyuv

import evergreen
from evergreen.futures import Future
from evergreen.io import errno
from evergreen.io.stream import BaseStream, StreamConnection, StreamServer
from evergreen.log import log

__all__ = ['PipeServer', 'PipeClient', 'PipeConnection', 'PipeStream', 'PipeError']


PipeError = pyuv.error.PipeError


class BasePipeStream(BaseStream):
    error_class = PipeError

    def __init__(self, handle):
        super(BasePipeStream, self).__init__()
        self._handle = handle

    def _read(self, n):
        read_result = Future()
        def cb(handle, data, error):
            self._handle.stop_read()
            if error is not None:
                read_result.set_exception(PipeError(error, pyuv.errno.strerror(error)))
            else:
                read_result.set_result(data)

        try:
            self._handle.start_read(cb)
        except PipeError:
            self.close()
            raise
        try:
            data = read_result.get()
        except PipeError as e:
            self.close()
            if e.args[0] != errno.EOF:
                raise
        else:
            self._read_buffer.feed(data)

    def _write(self, data):
        try:
            self._handle.write(data, self.__write_cb)
        except PipeError:
            self.close()
            raise

    def _close(self):
        self._handle.shutdown(self.__shutdown_cb)

    def __write_cb(self, handle, error):
        if error is not None:
            log.debug('write failed: %d %s', error, pyuv.errno.strerror(error))
            evergreen.current.loop.call_soon(self.close)

    def __shutdown_cb(self, handle, error):
        self._handle.close()


class PipeStream(BasePipeStream):

    def __init__(self):
        loop = evergreen.current.loop
        handle = pyuv.Pipe(loop._loop)
        super(PipeStream, self).__init__(handle)

    def open(self, fd):
        self._handle.open(fd)
        self._set_connected()


class PipeConnection(BasePipeStream, StreamConnection):
    pass


class PipeClient(BasePipeStream):

    def __init__(self):
        loop = evergreen.current.loop
        handle = pyuv.Pipe(loop._loop)
        super(PipeClient, self).__init__(handle)

    def connect(self, target):
        if self._connected:
            raise PipeError('already connected')

        connect_result = Future()
        def cb(handle, error):
            if error is not None:
                connect_result.set_exception(PipeError(error, pyuv.errno.strerror(error)))
            else:
                connect_result.set_result(None)

        try:
            self._handle.connect(target, cb)
        except PipeError:
            self.close()
            raise
        try:
            connect_result.get()
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
        self._handle.listen(self.__listen_cb, backlog)

    def _close(self):
        self._handle.close()

    def __listen_cb(self, handle, error):
        if error is not None:
            log.debug('listen failed: %d %s', error, pyuv.errno.strerror(error))
            return
        pipe_handle = pyuv.Pipe(self._handle.loop)
        try:
            self._handle.accept(pipe_handle)
        except PipeError as e:
            log.debug('accept failed: %d %s', e.args[0], pyuv.errno.strerror(e.args[1]))
            pipe_handle.close()
        else:
            conn = self.connection_class(pipe_handle)
            conn._set_accepted(self)
            self.handle_connection(conn)

