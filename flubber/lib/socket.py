# -*- coding: utf-8 -
#
# This file is part of flubber. See the NOTICE for more information.

from __future__ import absolute_import

import os
import _socket
import sys
import time
import warnings

import flubber
import pyuv

from flubber.event import Event
from flubber.patcher import slurp_properties
from flubber.timeout import Timeout

is_windows = sys.platform == 'win32'

if is_windows:
    from errno import WSAEINVAL as EINVAL
    from errno import WSAEWOULDBLOCK as EWOULDBLOCK
    from errno import WSAEINPROGRESS as EINPROGRESS
    from errno import WSAEALREADY as EALREADY
    from errno import WSAEISCONN as EISCONN
    EAGAIN = EWOULDBLOCK
else:
    from errno import EINVAL
    from errno import EWOULDBLOCK
    from errno import EINPROGRESS
    from errno import EALREADY
    from errno import EISCONN
    from errno import EAGAIN
from errno import EBADF

import socket as __socket__
__all__     = __socket__.__all__
__patched__ = ['fromfd', 'socketpair', 'ssl', 'socket', 'SocketType',
               'gethostbyname', 'gethostbyname_ex', 'getnameinfo', 'getaddrinfo',
               'create_connection',]

slurp_properties(__socket__, globals(), ignore=__patched__, srckeys=dir(__socket__))

_realsocket = _socket.socket
_fileobject = __socket__._fileobject


try:
    _GLOBAL_DEFAULT_TIMEOUT = __socket__._GLOBAL_DEFAULT_TIMEOUT
except AttributeError:
    _GLOBAL_DEFAULT_TIMEOUT = object()

try:
    __original_fromfd__ = __socket__.fromfd
    def fromfd(*args):
        return socket(__original_fromfd__(*args))
except AttributeError:
    pass

try:
    __original_socketpair__ = __socket__.socketpair
    def socketpair(*args):
        one, two = __original_socketpair__(*args)
        return socket(one), socket(two)
except AttributeError:
    pass

try:
    from flubber.lib import ssl as ssl_module
    sslerror = __socket__.sslerror
    __socket__.ssl
    def ssl(sock, certificate=None, private_key=None):
        warnings.warn("socket.ssl() is deprecated.  Use ssl.wrap_socket() instead.", DeprecationWarning, stacklevel=2)
        return ssl_module.sslwrap_simple(sock, private_key, certificate)
except Exception:
    # if the real socket module doesn't have the ssl method or sslerror
    # exception, we can't emulate them
    pass


def _get_memory(string, offset):
    try:
        return memoryview(string)[offset:]
    except TypeError:
        return buffer(string, offset)


class _closedsocket(object):
    __slots__ = []

    def _dummy(*args, **kwargs):
        raise error(EBADF, 'Bad file descriptor')
    # All _delegate_methods must also be initialized here.
    send = recv = recv_into = sendto = recvfrom = recvfrom_into = _dummy
    __getattr__ = _dummy


cancel_wait_ex = error(EBADF, 'File descriptor was closed by another task')


class IOWaiter(object):

    def __init__(self, fd):
        self.fd = fd
        self._closed = False
        self._read_event = Event()
        self._write_event = Event()

    def wait_read(self, timeout=None, timeout_exc=None):
        if self._closed:
            raise cancel_wait_ex
        self._read_event.clear()
        hub = flubber.current.hub
        handler = hub.add_reader(self.fd, self._read_event.set)
        try:
            self._wait(self._read_event, timeout, timeout_exc)
        finally:
            handler.cancel()
            hub.remove_reader(self.fd)

    def wait_write(self, timeout=None, timeout_exc=None):
        if self._closed:
            raise cancel_wait_ex
        self._write_event.clear()
        hub = flubber.current.hub
        handler = hub.add_writer(self.fd, self._write_event.set)
        try:
            self._wait(self._write_event, timeout, timeout_exc)
        finally:
            handler.cancel()
            hub.remove_writer(self.fd)

    def close(self):
        self._closed = True
        self._read_event.set()
        self._write_event.set()

    def _wait(self, event, timeout, timeout_exc):
        with Timeout(timeout, timeout_exc) as t:
            try:
                event.wait()
            except Timeout as e:
                if e is not t:
                    raise
        if self._closed:
            raise cancel_wait_ex

    def __repr__(self):
        return '<%s fd=%d>' % (self.__class__.__name__, self.fd)


class socket(object):

    def __init__(self, family=AF_INET, type=SOCK_STREAM, proto=0, _sock=None):
        if _sock is None:
            self._sock = _realsocket(family, type, proto)
            self.timeout = _socket.getdefaulttimeout()
        else:
            if hasattr(_sock, '_sock'):
                self._sock = _sock._sock
                self.timeout = getattr(_sock, 'timeout', False)
                if self.timeout is False:
                    self.timeout = _socket.getdefaulttimeout()
            else:
                self._sock = _sock
                self.timeout = _socket.getdefaulttimeout()
        self._sock.setblocking(0)
        self._io = IOWaiter(self._sock.fileno())

    def __repr__(self):
        return '<%s at %s %s>' % (type(self).__name__, hex(id(self)), self._formatinfo())

    def __str__(self):
        return '<%s %s>' % (type(self).__name__, self._formatinfo())

    def _formatinfo(self):
        try:
            fileno = self.fileno()
        except Exception:
            fileno = str(sys.exc_info()[1])
        try:
            sockname = self.getsockname()
            sockname = '%s:%s' % sockname
        except Exception:
            sockname = None
        try:
            peername = self.getpeername()
            peername = '%s:%s' % peername
        except Exception:
            peername = None
        result = 'fileno=%s' % fileno
        if sockname is not None:
            result += ' sock=' + str(sockname)
        if peername is not None:
            result += ' peer=' + str(peername)
        if getattr(self, 'timeout', None) is not None:
            result += ' timeout=' + str(self.timeout)
        return result

    def accept(self):
        sock = self._sock
        while True:
            try:
                client_socket, address = sock.accept()
                break
            except error:
                ex = sys.exc_info()[1]
                if ex[0] != EWOULDBLOCK or self.timeout == 0.0:
                    raise
                sys.exc_clear()
            self._io.wait_read(timeout=self.timeout, timeout_exc=timeout('timed out'))
        return socket(_sock=client_socket), address

    def close(self, _closedsocket=_closedsocket):
        # This function should not reference any globals. See Python issue #808164.
        self._io.close()
        self._sock = _closedsocket()

    @property
    def closed(self):
        return isinstance(self._sock, _closedsocket)

    def connect(self, address):
        if self.timeout == 0.0:
            return self._sock.connect(address)
        sock = self._sock
        if isinstance(address, tuple):
            hub = flubber.current.hub
            r = hub.threadpool.spawn(getaddrinfo, address[0], address[1], sock.family, sock.type, sock.proto).result()
            address = r[0][-1]
        timer = Timeout(self.timeout, timeout('timed out'))
        timer.start()
        try:
            while True:
                err = sock.getsockopt(SOL_SOCKET, SO_ERROR)
                if err:
                    raise error(err, os.strerror(err))
                result = sock.connect_ex(address)
                if not result or result == EISCONN:
                    break
                elif (result in (EWOULDBLOCK, EINPROGRESS, EALREADY)) or (result == EINVAL and is_windows):
                    self._io.wait_write()
                else:
                    raise error(result, os.strerror(result))
        finally:
            timer.cancel()

    def connect_ex(self, address):
        try:
            return self.connect(address) or 0
        except timeout:
            return EAGAIN
        except error:
            ex = sys.exc_info()[1]
            if type(ex) is error:
                return ex.args[0]
            else:
                raise  # gaierror is not silented by connect_ex

    def dup(self):
        """dup() -> socket object

        Return a new socket object connected to the same system resource.
        Note, that the new socket does not inherit the timeout."""
        return socket(_sock=self._sock)

    def makefile(self, mode='r', bufsize=-1):
        # Two things to look out for:
        # 1) Closing the original socket object should not close the
        #    socket (hence creating a new instance)
        # 2) The resulting fileobject must keep the timeout in order
        #    to be compatible with the stdlib's socket.makefile.
        return _fileobject(type(self)(_sock=self), mode, bufsize)

    def recv(self, *args):
        sock = self._sock  # keeping the reference so that fd is not closed during waiting
        while True:
            try:
                return sock.recv(*args)
            except error:
                ex = sys.exc_info()[1]
                if ex.args[0] != EWOULDBLOCK or self.timeout == 0.0:
                    raise
                # without clearing exc_info test__refcount.test_clean_exit fails
                sys.exc_clear()
            self._io.wait_read(timeout=self.timeout, timeout_exc=timeout('timed out'))

    def recvfrom(self, *args):
        sock = self._sock
        while True:
            try:
                return sock.recvfrom(*args)
            except error:
                ex = sys.exc_info()[1]
                if ex.args[0] != EWOULDBLOCK or self.timeout == 0.0:
                    raise
                sys.exc_clear()
            self._io.wait_read(timeout=self.timeout, timeout_exc=timeout('timed out'))

    def recvfrom_into(self, *args):
        sock = self._sock
        while True:
            try:
                return sock.recvfrom_into(*args)
            except error:
                ex = sys.exc_info()[1]
                if ex.args[0] != EWOULDBLOCK or self.timeout == 0.0:
                    raise
                sys.exc_clear()
            self._io.wait_read(timeout=self.timeout, timeout_exc=timeout('timed out'))

    def recv_into(self, *args):
        sock = self._sock
        while True:
            try:
                return sock.recv_into(*args)
            except error:
                ex = sys.exc_info()[1]
                if ex.args[0] != EWOULDBLOCK or self.timeout == 0.0:
                    raise
                sys.exc_clear()
            self._io.wait_read(timeout=self.timeout, timeout_exc=timeout('timed out'))

    def send(self, data, flags=0):
        sock = self._sock
        try:
            return sock.send(data, flags)
        except error:
            ex = sys.exc_info()[1]
            if ex.args[0] != EWOULDBLOCK or self.timeout == 0.0:
                raise
            sys.exc_clear()
            self._io.wait_write(timeout=self.timeout, timeout_exc=timeout('timed out'))
            try:
                return sock.send(data, flags)
            except error:
                ex2 = sys.exc_info()[1]
                if ex2.args[0] == EWOULDBLOCK:
                    return 0
                raise

    def sendall(self, data, flags=0):
        if self.timeout is None:
            data_sent = 0
            while data_sent < len(data):
                data_sent += self.send(_get_memory(data, data_sent), flags)
        else:
            timeleft = self.timeout
            end = time.time() + timeleft
            data_sent = 0
            while True:
                data_sent += self.send(_get_memory(data, data_sent), flags, timeout=timeleft)
                if data_sent >= len(data):
                    break
                timeleft = end - time.time()
                if timeleft <= 0:
                    raise timeout('timed out')

    def sendto(self, *args):
        sock = self._sock
        try:
            return sock.sendto(*args)
        except error:
            ex = sys.exc_info()[1]
            if ex.args[0] != EWOULDBLOCK or timeout == 0.0:
                raise
            sys.exc_clear()
            self._io.wait_write(timeout=self.timeout, timeout_exc=timeout('timed out'))
            try:
                return sock.sendto(*args)
            except error:
                ex2 = sys.exc_info()[1]
                if ex2.args[0] == EWOULDBLOCK:
                    return 0
                raise

    def setblocking(self, flag):
        if flag:
            self.timeout = None
        else:
            self.timeout = 0.0

    def settimeout(self, howlong):
        if howlong is not None:
            try:
                f = howlong.__float__
            except AttributeError:
                raise TypeError('a float is required')
            howlong = f()
            if howlong < 0.0:
                raise ValueError('Timeout value out of range')
        self.timeout = howlong

    def gettimeout(self):
        return self.timeout

    def shutdown(self, how):
        # TODO: close the io waiter?
        self._sock.shutdown(how)

    family = property(lambda self: self._sock.family, doc="the socket family")
    type = property(lambda self: self._sock.type, doc="the socket type")
    proto = property(lambda self: self._sock.proto, doc="the socket protocol")

    # delegate the functions that we haven't implemented to the real socket object

    _s = ("def %s(self, *args): return self._sock.%s(*args)\n\n"
          "%s.__doc__ = _realsocket.%s.__doc__\n")
    for _m in set(_socketmethods) - set(locals()):
        exec (_s % (_m, _m, _m, _m))
    del _m, _s

SocketType = socket


def _run_in_threadpool(func, *args, **kw):
    hub = flubber.current.hub
    return hub.threadpool.spawn(func, *args, **kw)


def gethostbyname(*args, **kw):
    return _run_in_threadpool(__socket__.gethostbyname, *args, **kw).result()


def gethostbyname_ex(*args, **kw):
    return _run_in_threadpool(__socket__.gethostbyname_ex, *args, **kw).result()


def getnameinfo(*args, **kw):
    return _run_in_threadpool(__socket__.getnameinfo, *args, **kw).result()


def getaddrinfo(*args, **kw):
    return _run_in_threadpool(__socket__.getaddrinfo, *args, **kw).result()


def create_connection(address, timeout=_GLOBAL_DEFAULT_TIMEOUT, source_address=None):
    """Connect to *address* and return the socket object.

    Convenience function.  Connect to *address* (a 2-tuple ``(host,
    port)``) and return the socket object.  Passing the optional
    *timeout* parameter will set the timeout on the socket instance
    before attempting to connect.  If no *timeout* is supplied, the
    global default timeout setting returned by :func:`getdefaulttimeout`
    is used. If *source_address* is set it must be a tuple of (host, port)
    for the socket to bind as a source address before making the connection.
    An host of '' or port 0 tells the OS to use the default.
    """

    host, port = address
    err = None
    for res in getaddrinfo(host, port, 0 if has_ipv6 else AF_INET, SOCK_STREAM):
        af, socktype, proto, _canonname, sa = res
        sock = None
        try:
            sock = socket(af, socktype, proto)
            if timeout is not _GLOBAL_DEFAULT_TIMEOUT:
                sock.settimeout(timeout)
            if source_address:
                sock.bind(source_address)
            sock.connect(sa)
            return sock
        except error:
            err = sys.exc_info()[1]
            # without exc_clear(), if connect() fails once, the socket is referenced by the frame in exc_info
            # and the next bind() fails, that does not happen with regular sockets though,
            #because _socket.socket.connect() is a built-in.
            sys.exc_clear()
            if sock is not None:
                sock.close()
    if err is not None:
        raise err
    else:
        raise error("getaddrinfo returns an empty list")

