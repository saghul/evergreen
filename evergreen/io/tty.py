#
# This file is part of Evergreen. See the NOTICE for more information.
#

import atexit
import os
import pyuv
import sys

import evergreen
from evergreen.io.stream import BaseStream, StreamError
from evergreen.io.util import Result
from evergreen.log import log

__all__ = ['TTYStream', 'TTYError', 'StdinStream', 'StdoutStream', 'StderrStream']


# Reset terminal settings on program exit
atexit.register(pyuv.TTY.reset_mode)


class TTYError(StreamError):
    pass


class TTYStream(BaseStream):
    error_class = TTYError

    def __init__(self, fd, readable):
        super(TTYStream, self).__init__()
        loop = evergreen.current.loop
        self._handle = pyuv.TTY(loop._loop, fd, readable)
        self._set_connected()

    @property
    def readable(self):
        return self._handle.readable

    @property
    def writable(self):
        return self._handle.writable

    @property
    def winsize(self):
        return self._handle.get_winsize()

    def set_mode(self, raw):
        self._handle.set_mode(raw)

    def _read(self, n):
        read_result = Result()
        def cb(handle, data, error):
            self._handle.stop_read()
            if error is not None:
                if error != pyuv.errno.UV_EOF:
                    read_result.set_exception(TTYError(error, pyuv.errno.strerror(error)))
                else:
                    read_result.set_result(b'')
            else:
                read_result.set_result(data)

        try:
            self._handle.start_read(cb)
        except pyuv.error.TTYError as e:
            self.close()
            raise TTYError(e.args[0], e.args[1])
        try:
            data = read_result.wait()
        except TTYError as e:
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
        except pyuv.error.TTYError as e:
            self.close()
            raise TTYError(e.args[0], e.args[1])

    def _close(self):
        self._handle.close()

    def __write_cb(self, handle, error):
        if error is not None:
            log.debug('write failed: %d %s', convert_errno(error), pyuv.errno.strerror(error))
            evergreen.current.loop.call_soon(self.close)


def StdinStream(fd=None):
    if not fd:
        fd = os.dup(sys.stdin.fileno())
    return TTYStream(fd, True)


def StdoutStream(fd=None):
    if not fd:
        fd = os.dup(sys.stdout.fileno())
    return TTYStream(fd, False)


def StderrStream(fd=None):
    if not fd:
        fd = os.dup(sys.stderr.fileno())
    return TTYStream(fd, False)

