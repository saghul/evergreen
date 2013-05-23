#
# This file is part of Evergreen. See the NOTICE for more information.
#

import pyuv
import re
import socket

from evergreen import six
from evergreen.event import Event
from evergreen.io.util import StringBuffer

__all__ = ['BaseStream', 'StreamConnection', 'StreamServer', 'StreamError']


StreamError = pyuv.error.StreamError


class BaseStream(object):
    error_class = None  # to be defined by subclass

    MAX_BUFFER_SIZE = 100*1024*1024
    READ_CHUNK_SIZE = 4*1024

    def __init__(self):
        self._read_buffer = StringBuffer(self.MAX_BUFFER_SIZE)
        self._write_buffer = []

        self._connected = False
        self._closed = False

    def read_bytes(self, nbytes):
        assert isinstance(nbytes, six.integer_types)
        assert nbytes > 0
        return self._do_read(nbytes=nbytes)

    def read_until(self, delimiter):
        return self._do_read(delimiter=delimiter)

    def read_until_regex(self, regex):
        return self._do_read(regex=re.compile(regex))

    def write(self, data):
        self._check_closed()
        if not self._connected:
            self._write_buffer.append(data)
            return False
        else:
            return self._write(data)

    def shutdown(self):
        self._check_closed()
        self._shutdown()

    def close(self):
        if self._closed:
            return
        self._read_buffer.clear()
        self._write_buffer = []
        self._close()
        self._closed = True

    @property
    def closed(self):
        return self._closed

    def _set_connected(self):
        self._connected = True
        buf, self._write_buffer = self._write_buffer, []
        if buf:
            self._write(b''.join(buf))

    # internal

    def _do_read(self, delimiter=None, nbytes=None, regex=None):
        # See if we've already got the data from a previous read
        data = self._read_from_buffer(delimiter, nbytes, regex)
        if data is not None:
            return data
        self._check_closed()
        while not self.closed:
            self._read(self.READ_CHUNK_SIZE)
            data = self._read_from_buffer(delimiter, nbytes, regex)
            if data is not None:
                return data
        return b''

    def _read_from_buffer(self, delimiter=None, nbytes=None, regex=None):
        if nbytes is not None:
            return self._read_buffer.read(nbytes)
        elif delimiter is not None:
            return self._read_buffer.read_until(delimiter)
        elif regex is not None:
            return self._read_buffer.read_until_regex(regex)

    def _check_closed(self):
        if self._closed:
            raise self.error_class('stream is closed')

    # internal, to be implemented by subclasses

    def _read(self, n):
        raise NotImplementedError

    def _write(self, data):
        raise NotImplementedError

    def _shutdown(self):
        raise NotImplementedError

    def _close(self):
        raise NotImplementedError


class StreamConnection(BaseStream):

    @property
    def server(self):
        return self._server

    def close(self):
        super(StreamConnection, self).close()
        if self._server:
            self._server.connections.remove(self)
            self._server = None

    def _set_accepted(self, server):
        # To be called by the server
        self._server = server
        self._server.connections.append(self)
        self._set_connected()


class StreamServer(object):
    error_class = None  # to be defined by subclass

    def __init__(self):
        self._end_event = Event()
        self._closed = False
        self.connections = []

    def handle_connection(self, connection):
        raise NotImplementedError

    def bind(self, address):
        self._check_closed()
        self._bind(address)

    def serve(self, backlog=None):
        self._check_closed()
        backlog = backlog or getattr(socket, 'SOMAXCONN', 128)
        self._serve(backlog)
        self._end_event.wait()

    def close(self):
        if not self._closed:
            self._close()
            self._closed = True
            for conn in self.connections[:]:
                conn.close()
            self._end_event.set()

    def _check_closed(self):
        if self._closed:
            raise self.error_class('server is closed')

    def _bind(self, address):
        raise NotImplementedError

    def _serve(self, backlog):
        raise NotImplementedError

    def _close(self):
        raise NotImplementedError

