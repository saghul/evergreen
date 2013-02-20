# -*- coding: utf-8 -
#
# This file is part of flubber. See the NOTICE for more information.

#TODO: broken, fix
from __future__ import absolute_import

import errno
import socket

import flubber

from flubber.io import IOWaiter, Pipe
from flubber.patcher import slurp_properties

import os as __os__
__all__ = __os__.__all__
__patched__ = ['fdopen', 'read', 'write', 'wait', 'waitpid']

slurp_properties(__os__, globals(), ignore=__patched__, srckeys=dir(__os__))
del slurp_properties


def fdopen(fd, *args, **kw):
    """fdopen(fd [, mode='r' [, bufsize]]) -> file_object

    Return an open file object connected to a file descriptor."""
    if not isinstance(fd, int):
        raise TypeError('fd should be int, not %r' % fd)
    try:
        return Pipe(fd, *args, **kw)
    except IOError, e:
        raise OSError(*e.args)


__original_read__ = __os__.read

def read(fd, n):
    """read(fd, buffersize) -> string

    Read a file descriptor."""
    io = IOWaiter(fd)
    while True:
        try:
            return __original_read__(fd, n)
        except (OSError, IOError), e:
            if e.args[0] != errno.EAGAIN:
                raise
        except socket.error, e:
            if e.args[0] == errno.EPIPE:
                return ''
            raise
        io.wait_read()


__original_write__ = __os__.write

def write(fd, st):
    """write(fd, string) -> byteswritten

    Write a string to a file descriptor.
    """
    io = IOWaiter(fd)
    while True:
        try:
            return __original_write__(fd, st)
        except (OSError, IOError), e:
            if e.args[0] != errno.EAGAIN:
                raise
        except socket.error, e:
            if e.args[0] != errno.EPIPE:
                raise
        io.wait_write()


def wait():
    """wait() -> (pid, status)

    Wait for completion of a child process."""
    return waitpid(0,0)


__original_waitpid__ = __os__.waitpid

def waitpid(pid, options):
    """waitpid(...)
    waitpid(pid, options) -> (pid, status)

    Wait for completion of a given child process."""
    if options & __os__.WNOHANG != 0:
        return __original_waitpid__(pid, options)
    else:
        new_options = options | __os__.WNOHANG
        while True:
            rpid, status = __original_waitpid__(pid, new_options)
            if rpid and status >= 0:
                return rpid, status
            flubber.yield_()

