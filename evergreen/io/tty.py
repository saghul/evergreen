#
# This file is part of Evergreen. See the NOTICE for more information.
#

import atexit
import os
import pyuv
import sys

import evergreen
from evergreen.io.stream import BaseStream

__all__ = ['TTYStream', 'TTYError', 'StdinStream', 'StdoutStream', 'StderrStream']


# Reset terminal settings on program exit
atexit.register(pyuv.TTY.reset_mode)


TTYError = pyuv.error.TTYError


class TTYStream(BaseStream):
    error_class = TTYError

    def __init__(self, fd, readable):
        super(TTYStream, self).__init__()
        loop = evergreen.current.loop
        self._handle = pyuv.TTY(loop._loop, fd, readable)
        self._set_connected()

    @property
    def winsize(self):
        return self._handle.get_winsize()

    def set_raw_mode(self, raw):
        self._handle.set_mode(raw)


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

