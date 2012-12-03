
from __future__ import absolute_import

import array
import os
import sys
import time

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

from errno import ENOTCONN
try:
    from errno import EBADF
except ImportError:
    EBADF = 9

import _socket
_realsocket = _socket.socket
import socket as __socket__
from socket import _fileobject, error, timeout

import ssl as __ssl__
_ssl = __ssl__._ssl
from ssl import SSLError, SSL_ERROR_EOF, SSL_ERROR_WANT_READ, SSL_ERROR_WANT_WRITE

import pyuv
import flubber

from flubber.core.hub import trampoline
from flubber.event import Event
from flubber.timeout import Timeout

__all__ = ['Socket', 'SSLSocket', 'Pipe']


class IOWaiter(object):

    def __init__(self, fd):
        self.fd = fd
        hub = flubber.current.hub
        self._handle = pyuv.Poll(hub.loop, fd)
        self._events = 0
        self._closed_error = None
        self._read_event = Event()
        self._write_event = Event()

    def wait_read(self, timeout=None, timeout_exc=None):
        if self._closed_error is not None:
            raise self._closed_error
        self._read_event.clear()
        self._events |= pyuv.UV_READABLE
        self._handle.start(self._events, self._poll_cb)
        self._wait(self._read_event, timeout, timeout_exc)

    def wait_write(self, timeout=None, timeout_exc=None):
        if self._closed_error is not None:
            raise self._closed_error
        self._write_event.clear()
        self._events |= pyuv.UV_WRITABLE
        self._handle.start(self._events, self._poll_cb)
        self._wait(self._write_event, timeout, timeout_exc)

    def close(self, error):
        self._closed_error = error
        self._handle.close()
        self._events = 0
        self._read_event.set()
        self._write_event.set()

    def _wait(self, event, timeout, timeout_exc):
        with Timeout(timeout, timeout_exc) as t:
            try:
                event.wait()
            except Timeout as e:
                if e is not t:
                    raise
        if self._closed_error is not None:
            raise self._closed_error

    def _poll_cb(self, handle, events, error):
        if error is not None:
            # There was an error, signal both readability and writablity so that waiters
            # can get the error
            self._events = 0
            self._read_event.set()
            self._write_event.set()
        else:
            if events & pyuv.UV_READABLE:
                self._events & ~pyuv.UV_READABLE
                self._read_event.set()
            if events & pyuv.UV_WRITABLE:
                self._events & ~pyuv.UV_WRITABLE
                self._write_event.set()
        if self._events == 0:
            self._handle.stop()
        else:
            self._handle.start(self._events, self._poll_cb)

    def __repr__(self):
        return '<%s fd=%d>' % (self.__class__.__name__, self.fd)


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


class Socket(object):

    def __init__(self, family=__socket__.AF_INET, type=__socket__.SOCK_STREAM, proto=0, _sock=None):
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
        return Socket(_sock=client_socket), address

    def close(self, _closedsocket=_closedsocket, cancel_wait_ex=cancel_wait_ex):
        # This function should not reference any globals. See Python issue #808164.
        self._io.close(cancel_wait_ex)
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
            r = hub.threadpool.spawn(__socket__.getaddrinfo, address[0], address[1], sock.family, sock.type, sock.proto).result()
            address = r[0][-1]
        timer = Timeout(self.timeout, timeout('timed out'))
        timer.start()
        try:
            while True:
                err = sock.getsockopt(__socket__.SOL_SOCKET, __socket__.SO_ERROR)
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
        return Socket(_sock=self._sock)

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
    for _m in set(__socket__._socketmethods) - set(locals()):
        exec (_s % (_m, _m, _m, _m))
    del _m, _s


if sys.version_info >= (2,7):
    ssl_timeout_exc = SSLError
else:
    ssl_timeout_exc = timeout

_SSLErrorReadTimeout = ssl_timeout_exc('The read operation timed out')
_SSLErrorWriteTimeout = ssl_timeout_exc('The write operation timed out')
_SSLErrorHandshakeTimeout = ssl_timeout_exc('The handshake operation timed out')


class SSLSocket(Socket):

    def __init__(self, sock, keyfile=None, certfile=None,
                 server_side=False, cert_reqs=__ssl__.CERT_NONE,
                 ssl_version=__ssl__.PROTOCOL_SSLv23, ca_certs=None,
                 do_handshake_on_connect=True,
                 suppress_ragged_eofs=True,
                 ciphers=None):
        Socket.__init__(self, _sock=sock)

        if certfile and not keyfile:
            keyfile = certfile
        # see if it's connected
        try:
            Socket.getpeername(self)
        except error, e:
            if e[0] != ENOTCONN:
                raise
            # no, no connection yet
            self._sslobj = None
        else:
            # yes, create the SSL object
            if ciphers is None:
                self._sslobj = _ssl.sslwrap(self._sock, server_side,
                                            keyfile, certfile,
                                            cert_reqs, ssl_version, ca_certs)
            else:
                self._sslobj = _ssl.sslwrap(self._sock, server_side,
                                            keyfile, certfile,
                                            cert_reqs, ssl_version, ca_certs,
                                            ciphers)
            if do_handshake_on_connect:
                self.do_handshake()
        self.keyfile = keyfile
        self.certfile = certfile
        self.cert_reqs = cert_reqs
        self.ssl_version = ssl_version
        self.ca_certs = ca_certs
        self.ciphers = ciphers
        self.do_handshake_on_connect = do_handshake_on_connect
        self.suppress_ragged_eofs = suppress_ragged_eofs
        self._makefile_refs = 0

    def read(self, len=1024):
        """Read up to LEN bytes and return them.
        Return zero-length string on EOF."""
        while True:
            try:
                return self._sslobj.read(len)
            except SSLError:
                ex = sys.exc_info()[1]
                if ex.args[0] == SSL_ERROR_EOF and self.suppress_ragged_eofs:
                    return ''
                elif ex.args[0] == SSL_ERROR_WANT_READ:
                    if self.timeout == 0.0:
                        raise
                    sys.exc_clear()
                    self._io.wait_read(timeout=self.timeout, timeout_exc=_SSLErrorReadTimeout)
                elif ex.args[0] == SSL_ERROR_WANT_WRITE:
                    if self.timeout == 0.0:
                        raise
                    sys.exc_clear()
                    self._io.wait_write(timeout=self.timeout, timeout_exc=_SSLErrorReadTimeout)
                else:
                    raise

    def write(self, data):
        """Write DATA to the underlying SSL channel.  Returns
        number of bytes of DATA actually transmitted."""
        while True:
            try:
                return self._sslobj.write(data)
            except SSLError:
                ex = sys.exc_info()[1]
                if ex.args[0] == SSL_ERROR_WANT_READ:
                    if self.timeout == 0.0:
                        raise
                    sys.exc_clear()
                    self._io.wait_read(timeout=self.timeout, timeout_exc=_SSLErrorWriteTimeout)
                elif ex.args[0] == SSL_ERROR_WANT_WRITE:
                    if self.timeout == 0.0:
                        raise
                    sys.exc_clear()
                    self._io.wait_write(timeout=self.timeout, timeout_exc=_SSLErrorWriteTimeout)
                else:
                    raise

    def getpeercert(self, binary_form=False):
        """Returns a formatted version of the data in the
        certificate provided by the other end of the SSL channel.
        Return None if no certificate was provided, {} if a
        certificate was provided, but not validated."""
        return self._sslobj.peer_certificate(binary_form)

    def cipher(self):
        if not self._sslobj:
            return None
        else:
            return self._sslobj.cipher()

    def send(self, data, flags=0):
        if self._sslobj:
            if flags != 0:
                raise ValueError("non-zero flags not allowed in calls to send() on %s" % self.__class__)
            while True:
                try:
                    v = self._sslobj.write(data)
                except SSLError:
                    x = sys.exc_info()[1]
                    if x.args[0] == SSL_ERROR_WANT_READ:
                        if self.timeout == 0.0:
                            return 0
                        sys.exc_clear()
                        self._io.wait_read(timeout=self.timeout, timeout_exc=timeout('timed out'))
                    elif x.args[0] == SSL_ERROR_WANT_WRITE:
                        if self.timeout == 0.0:
                            return 0
                        sys.exc_clear()
                        self._io.wait_write(timeout=self.timeout, timeout_exc=timeout('timed out'))
                    else:
                        raise
                else:
                    return v
        else:
            return Socket.send(self, data, flags)

    def sendto(self, *args):
        if self._sslobj:
            raise ValueError("sendto not allowed on instances of %s" % self.__class__)
        else:
            return Socket.sendto(self, *args)

    def recv(self, buflen=1024, flags=0):
        if self._sslobj:
            if flags != 0:
                raise ValueError("non-zero flags not allowed in calls to recv() on %s" % self.__class__)
            # Shouldn't we wrap the SSL_WANT_READ errors as socket.timeout errors to match socket.recv's behavior?
            return self.read(buflen)
        else:
            return Socket.recv(self, buflen, flags)

    def recv_into(self, buffer, nbytes=None, flags=0):
        if buffer and (nbytes is None):
            nbytes = len(buffer)
        elif nbytes is None:
            nbytes = 1024
        if self._sslobj:
            if flags != 0:
                raise ValueError("non-zero flags not allowed in calls to recv_into() on %s" % self.__class__)
            while True:
                try:
                    tmp_buffer = self.read(nbytes)
                    v = len(tmp_buffer)
                    buffer[:v] = tmp_buffer
                    return v
                except SSLError:
                    x = sys.exc_info()[1]
                    if x.args[0] == SSL_ERROR_WANT_READ:
                        if self.timeout == 0.0:
                            raise
                        sys.exc_clear()
                        self._io.wait_read(timeout=self.timeout, timeout_exc=timeout('timed out'))
                        continue
                    else:
                        raise
        else:
            return Socket.recv_into(self, buffer, nbytes, flags)

    def recvfrom(self, *args):
        if self._sslobj:
            raise ValueError("recvfrom not allowed on instances of %s" % self.__class__)
        else:
            return Socket.recvfrom(self, *args)

    def recvfrom_into(self, *args):
        if self._sslobj:
            raise ValueError("recvfrom_into not allowed on instances of %s" % self.__class__)
        else:
            return Socket.recvfrom_into(self, *args)

    def pending(self):
        if self._sslobj:
            return self._sslobj.pending()
        else:
            return 0

    def _sslobj_shutdown(self):
        while True:
            try:
                return self._sslobj.shutdown()
            except SSLError:
                ex = sys.exc_info()[1]
                if ex.args[0] == SSL_ERROR_EOF and self.suppress_ragged_eofs:
                    return ''
                elif ex.args[0] == SSL_ERROR_WANT_READ:
                    if self.timeout == 0.0:
                        raise
                    sys.exc_clear()
                    self._io.wait_read(timeout=self.timeout, timeout_exc=_SSLErrorReadTimeout)
                elif ex.args[0] == SSL_ERROR_WANT_WRITE:
                    if self.timeout == 0.0:
                        raise
                    sys.exc_clear()
                    self._io.wait_write(timeout=self.timeout, timeout_exc=_SSLErrorWriteTimeout)
                else:
                    raise

    def unwrap(self):
        if self._sslobj:
            s = self._sslobj_shutdown()
            self._sslobj = None
            return Socket(_sock=s)
        else:
            raise ValueError("No SSL wrapper around " + str(self))

    def shutdown(self, how):
        self._sslobj = None
        Socket.shutdown(self, how)

    def close(self):
        if self._makefile_refs < 1:
            self._sslobj = None
            Socket.close(self)
        else:
            self._makefile_refs -= 1

    def do_handshake(self):
        """Perform a TLS/SSL handshake."""
        while True:
            try:
                return self._sslobj.do_handshake()
            except SSLError:
                ex = sys.exc_info()[1]
                if ex.args[0] == SSL_ERROR_WANT_READ:
                    if self.timeout == 0.0:
                        raise
                    sys.exc_clear()
                    self._io.wait_read(timeout=self.timeout, timeout_exc=_SSLErrorHandshakeTimeout)
                elif ex.args[0] == SSL_ERROR_WANT_WRITE:
                    if self.timeout == 0.0:
                        raise
                    sys.exc_clear()
                    self._io.wait_write(timeout=self.timeout, timeout_exc=_SSLErrorHandshakeTimeout)
                else:
                    raise

    def connect(self, addr):
        """Connects to remote ADDR, and then wraps the connection in
        an SSL channel."""
        # Here we assume that the socket is client-side, and not
        # connected at the time of the call.  We connect it, then wrap it.
        if self._sslobj:
            raise ValueError("attempt to connect already-connected SSLSocket!")
        Socket.connect(self, addr)
        if self.ciphers is None:
            self._sslobj = _ssl.sslwrap(self._sock, False, self.keyfile, self.certfile,
                                        self.cert_reqs, self.ssl_version,
                                        self.ca_certs)
        else:
            self._sslobj = _ssl.sslwrap(self._sock, False, self.keyfile, self.certfile,
                                        self.cert_reqs, self.ssl_version,
                                        self.ca_certs, self.ciphers)
        if self.do_handshake_on_connect:
            self.do_handshake()

    def accept(self):
        """Accepts a new connection from a remote client, and returns
        a tuple containing that new connection wrapped with a server-side
        SSL channel, and the address of the remote client."""
        newsock, addr = Socket.accept(self)
        ssl_sock = SSLSocket(newsock._sock,
                             keyfile=self.keyfile,
                             certfile=self.certfile,
                             server_side=True,
                             cert_reqs=self.cert_reqs,
                             ssl_version=self.ssl_version,
                             ca_certs=self.ca_certs,
                             do_handshake_on_connect=self.do_handshake_on_connect,
                             suppress_ragged_eofs=self.suppress_ragged_eofs,
                             ciphers=self.ciphers)
        return ssl_sock, addr

    def makefile(self, mode='r', bufsize=-1):
        """Make and return a file-like object that
        works with the SSL connection.  Just use the code
        from the socket module."""
        self._makefile_refs += 1
        # close=True so as to decrement the reference count when done with
        # the file-like object.
        return _fileobject(self, mode, bufsize, close=True)


class _SocketDuckForFd(object):
    """ Class implementing all socket method used by _fileobject in cooperative manner using low level os I/O calls."""
    def __init__(self, fileno):
        self._fileno = fileno
        # TODO: don't use trampoline here

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
            trampoline(self, read=True)

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
        while total_sent <len_data:
            trampoline(self, write=True)
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
    GreenPipe is a cooperative replacement for file class.
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
        # TODO fix this
        #set_nonblocking(self)
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
        data = self.read(len(buf)) #FIXME could it be done without allocating intermediate?
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

