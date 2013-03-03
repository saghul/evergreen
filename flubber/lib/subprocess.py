#
# This file is part of flubber. See the NOTICE for more information.
#

#TODO: broken, fix
from __future__ import absolute_import

import array
import errno
import new
import os
import sys

import flubber

from flubber import patcher
from flubber.lib import select
from flubber.socket import IOWaiter, _fileobject

is_windows = sys.platform == 'win32'

if is_windows:
    from errno import WSAEWOULDBLOCK as EWOULDBLOCK
    EAGAIN = EWOULDBLOCK
else:
    from errno import EAGAIN

patcher.inject('subprocess', globals(), ('select', select))
import subprocess as __subprocess__


class _SocketDuckForFd(object):
    """ Class implementing all socket method used by _fileobject in cooperative manner using low level os I/O calls."""
    def __init__(self, fileno):
        self._fileno = fileno
        self._io = IOWaiter(fileno)

    @property
    def _sock(self):
        return self

    def fileno(self):
        return self._fileno

    def recv(self, buflen):
        while True:
            try:
                data = os.read(self._fileno, buflen)
                return data
            except OSError, e:
                if e.args[0] != EAGAIN:
                    raise IOError(*e.args)
            self._io.wait_read()

    def sendall(self, data):
        len_data = len(data)
        os_write = os.write
        fileno = self._fileno
        try:
            total_sent = os_write(fileno, data)
        except OSError, e:
            if e.args[0] != EAGAIN:
                raise IOError(*e.args)
            total_sent = 0
        while total_sent < len_data:
            self._io.wait_write()
            try:
                total_sent += os_write(fileno, data[total_sent:])
            except OSError, e:
                if e.args[0] != EAGAIN:
                    raise IOError(*e.args)

    def __del__(self):
        try:
            os.close(self._fileno)
        except:
            # os.close may fail if __init__ didn't complete (i.e file dscriptor passed to popen was invalid
            pass

    def __repr__(self):
        return "%s:%d" % (self.__class__.__name__, self._fileno)


def _operationOnClosedFile(*args, **kwargs):
    raise ValueError("I/O operation on closed file")


class Pipe(_fileobject):
    """
    Pipe is a cooperative replacement for file class.
    It will cooperate on pipes. It will block on regular file.
    Differneces from file class:
    - mode is r/w property. Should re r/o
    - encoding property not implemented
    - write/writelines will not raise TypeError exception when non-string data is written
      it will write str(data) instead
    - Universal new lines are not supported and newlines property not implementeded
    - file argument can be descriptor, file name or file object.
    """
    def __init__(self, f, mode='r', bufsize=-1):
        if not isinstance(f, (basestring, int, file)):
            raise TypeError('f(ile) should be int, str, unicode or file, not %r' % f)

        if isinstance(f, basestring):
            f = open(f, mode, 0)

        if isinstance(f, int):
            fileno = f
            self._name = "<fd:%d>" % fileno
        else:
            fileno = os.dup(f.fileno())
            self._name = f.name
            if f.mode != mode:
                raise ValueError('file.mode %r does not match mode parameter %r' % (f.mode, mode))
            self._name = f.name
            f.close()

        super(Pipe, self).__init__(_SocketDuckForFd(fileno), mode, bufsize)
        self._set_nonblocking(self)
        self.softspace = 0

    @property
    def name(self):
        return self._name

    def __repr__(self):
        return "<%s %s %r, mode %r at 0x%x>" % (
            self.closed and 'closed' or 'open',
            self.__class__.__name__,
            self.name,
            self.mode,
            id(self))

    def close(self):
        super(Pipe, self).close()
        for method in ['fileno', 'flush', 'isatty', 'next', 'read', 'readinto',
                   'readline', 'readlines', 'seek', 'tell', 'truncate',
                   'write', 'xreadlines', '__iter__', 'writelines']:
            setattr(self, method, _operationOnClosedFile)

    if getattr(file, '__enter__', None):
        def __enter__(self):
            return self

        def __exit__(self, *args):
            self.close()

    def xreadlines(self, buffer):
        return iter(self)

    def readinto(self, buf):
        #FIXME could it be done without allocating intermediate?
        data = self.read(len(buf))
        n = len(data)
        try:
            buf[:n] = data
        except TypeError, err:
            if not isinstance(buf, array.array):
                raise err
            buf[:n] = array.array('c', data)
        return n

    def _get_readahead_len(self):
        return len(self._rbuf.getvalue())

    def _clear_readahead_buf(self):
        len = self._get_readahead_len()
        if len>0:
            self.read(len)

    def tell(self):
        self.flush()
        try:
            return os.lseek(self.fileno(), 0, 1) - self._get_readahead_len()
        except OSError, e:
            raise IOError(*e.args)

    def seek(self, offset, whence=0):
        self.flush()
        if whence == 1 and offset==0: # tell synonym
            return self.tell()
        if whence == 1: # adjust offset by what is read ahead
            offset -= self.get_readahead_len()
        try:
            rv = os.lseek(self.fileno(), offset, whence)
        except OSError, e:
            raise IOError(*e.args)
        else:
            self._clear_readahead_buf()
            return rv

    if getattr(file, "truncate", None): # not all OSes implement truncate
        def truncate(self, size=-1):
            self.flush()
            if size ==-1:
                size = self.tell()
            try:
                rv = os.ftruncate(self.fileno(), size)
            except OSError, e:
                raise IOError(*e.args)
            else:
                self.seek(size) # move position&clear buffer
                return rv

    def isatty(self):
        try:
            return os.isatty(self.fileno())
        except OSError, e:
            raise IOError(*e.args)

    def _set_nonblocking(self, fd):
        """
        Sets the descriptor to be nonblocking.  Works on many file-like
        objects as well as sockets.  Only sockets can be nonblocking on
        Windows, however.
        """
        try:
            setblocking = fd.setblocking
        except AttributeError:
            # fd has no setblocking() method. It could be that this version of
            # Python predates socket.setblocking(). In that case, we can still set
            # the flag "by hand" on the underlying OS fileno using the fcntl
            # module.
            try:
                import fcntl
            except ImportError:
                # Whoops, Windows has no fcntl module. This might not be a socket
                # at all, but rather a file-like object with no setblocking()
                # method. In particular, on Windows, pipes don't support
                # non-blocking I/O and therefore don't have that method. Which
                # means fcntl wouldn't help even if we could load it.
                raise NotImplementedError("set_nonblocking() on a file object "
                                        "with no setblocking() method "
                                        "(Windows pipes don't support non-blocking I/O)")
            # We managed to import fcntl.
            fileno = fd.fileno()
            flags = fcntl.fcntl(fileno, fcntl.F_GETFL)
            fcntl.fcntl(fileno, fcntl.F_SETFL, flags | os.O_NONBLOCK)
        else:
            # socket supports setblocking()
            setblocking(0)


# This is the meat of this module, the green version of Popen.
class Popen(__subprocess__.Popen):
    """flubber-friendly version of subprocess.Popen"""
    # We do not believe that Windows pipes support non-blocking I/O. At least,
    # the Python file objects stored on our base-class object have no
    # setblocking() method, and the Python fcntl module doesn't exist on
    # Windows. As the sole purpose of
    # this __init__() override is to wrap the pipes for flubber-friendly
    # non-blocking I/O, don't even bother overriding it on Windows.
    if not __subprocess__.mswindows:
        def __init__(self, args, bufsize=0, *argss, **kwds):
            # Forward the call to base-class constructor
            __subprocess__.Popen.__init__(self, args, 0, *argss, **kwds)
            # Now wrap the pipes, if any. This logic is loosely borrowed from
            # flubber.processes.Process.run() method.
            for attr in "stdin", "stdout", "stderr":
                pipe = getattr(self, attr)
                if pipe is not None and not type(pipe) is Pipe:
                    wrapped_pipe = Pipe(pipe, pipe.mode, bufsize)
                    setattr(self, attr, wrapped_pipe)
        __init__.__doc__ = __subprocess__.Popen.__init__.__doc__

    def wait(self, check_interval=0.01):
        # Instead of a blocking OS call, this version of wait() uses logic
        # borrowed from the flubber 0.2 processes.Process.wait() method.
        try:
            while True:
                status = self.poll()
                if status is not None:
                    return status
                flubber.sleep(check_interval)
        except OSError, e:
            if e.errno == errno.ECHILD:
                # no child process, this happens if the child process
                # already died and has been cleaned up
                return -1
            else:
                raise
    wait.__doc__ = __subprocess__.Popen.wait.__doc__

    if not __subprocess__.mswindows:
        # don't want to rewrite the original _communicate() method, we
        # just want a version that uses flubber.lib.select.select()
        # instead of select.select().
        try:
            _communicate = new.function(__subprocess__.Popen._communicate.im_func.func_code,
                                        globals())
        except AttributeError:
            # 2.4 only has communicate
            _communicate = new.function(__subprocess__.Popen.communicate.im_func.func_code,
                                        globals())
            def communicate(self, input=None):
                return self._communicate(input)

# Borrow subprocess.call() and check_call(), but patch them so they reference
# OUR Popen class rather than subprocess.Popen.
call = new.function(__subprocess__.call.func_code, globals())
check_call = new.function(__subprocess__.check_call.func_code, globals())

