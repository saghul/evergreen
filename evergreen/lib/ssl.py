#
# This file is part of Evergreen. See the NOTICE for more information.
#

from __future__ import absolute_import

import errno
import sys

from evergreen import six
from evergreen.lib.socket import socket, _fileobject
from evergreen.lib.socket import error as socket_error, timeout as socket_timeout
from evergreen.patcher import slurp_properties

import ssl as __ssl__
__patched__ = ['SSLSocket', 'wrap_socket', 'socket', 'sslwrap_simple']

slurp_properties(__ssl__, globals(), ignore=__patched__, srckeys=dir(__ssl__))
del slurp_properties

_ssl = __ssl__._ssl


if sys.version_info >= (2, 7):
    ssl_timeout_exc = SSLError
else:
    ssl_timeout_exc = socket_timeout

_SSLErrorReadTimeout = ssl_timeout_exc('The read operation timed out')
_SSLErrorWriteTimeout = ssl_timeout_exc('The write operation timed out')
_SSLErrorHandshakeTimeout = ssl_timeout_exc('The handshake operation timed out')


class SSLSocket(socket):

    def __init__(self, sock, keyfile=None, certfile=None,
                 server_side=False, cert_reqs=CERT_NONE,
                 ssl_version=PROTOCOL_SSLv23, ca_certs=None,
                 do_handshake_on_connect=True,
                 suppress_ragged_eofs=True,
                 ciphers=None, server_hostname=None, _context=None):
        socket.__init__(self, _sock=sock)

        if certfile and not keyfile:
            keyfile = certfile
        # see if it's connected
        try:
            socket.getpeername(self)
        except socket_error as e:
            if e.args[0] != errno.ENOTCONN:
                raise
            # no, no connection yet
            self._sslobj = None
        else:
            # yes, create the SSL object
            if six.PY3:
                self._sslobj = None
                if _context:
                    self.context = _context
                else:
                    if server_side and not certfile:
                        raise ValueError("certfile must be specified for server-side operations")
                    if keyfile and not certfile:
                        raise ValueError("certfile must be specified")
                    if certfile and not keyfile:
                        keyfile = certfile
                    self.context = __ssl__._SSLContext(ssl_version)
                    self.context.verify_mode = cert_reqs
                    if ca_certs:
                        self.context.load_verify_locations(ca_certs)
                    if certfile:
                        self.context.load_cert_chain(certfile, keyfile)
                    if ciphers:
                        self.context.set_ciphers(ciphers)
                if server_side and server_hostname:
                    raise ValueError("server_hostname can only be specified in client mode")
                self.server_hostname = server_hostname
                try:
                    self._sslobj = self.context._wrap_socket(self._sock, server_side, server_hostname)
                except socket_error:
                    self.close()
                    raise
            else:
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
                    return b''
                elif ex.args[0] == SSL_ERROR_WANT_READ:
                    if self.timeout == 0.0:
                        raise
                    six.exc_clear()
                    self._io.wait_read(timeout=self.timeout, timeout_exc=_SSLErrorReadTimeout)
                elif ex.args[0] == SSL_ERROR_WANT_WRITE:
                    if self.timeout == 0.0:
                        raise
                    six.exc_clear()
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
                    six.exc_clear()
                    self._io.wait_read(timeout=self.timeout, timeout_exc=_SSLErrorWriteTimeout)
                elif ex.args[0] == SSL_ERROR_WANT_WRITE:
                    if self.timeout == 0.0:
                        raise
                    six.exc_clear()
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
                        six.exc_clear()
                        self._io.wait_read(timeout=self.timeout, timeout_exc=socket_timeout('timed out'))
                    elif x.args[0] == SSL_ERROR_WANT_WRITE:
                        if self.timeout == 0.0:
                            return 0
                        six.exc_clear()
                        self._io.wait_write(timeout=self.timeout, timeout_exc=socket_timeout('timed out'))
                    else:
                        raise
                else:
                    return v
        else:
            return socket.send(self, data, flags)

    def sendto(self, *args):
        if self._sslobj:
            raise ValueError("sendto not allowed on instances of %s" % self.__class__)
        else:
            return socket.sendto(self, *args)

    def recv(self, buflen=1024, flags=0):
        if self._sslobj:
            if flags != 0:
                raise ValueError("non-zero flags not allowed in calls to recv() on %s" % self.__class__)
            # Shouldn't we wrap the SSL_WANT_READ errors as socket.timeout errors to match socket.recv's behavior?
            return self.read(buflen)
        else:
            return socket.recv(self, buflen, flags)

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
                        six.exc_clear()
                        self._io.wait_read(timeout=self.timeout, timeout_exc=socket_timeout('timed out'))
                        continue
                    else:
                        raise
        else:
            return socket.recv_into(self, buffer, nbytes, flags)

    def recvfrom(self, *args):
        if self._sslobj:
            raise ValueError("recvfrom not allowed on instances of %s" % self.__class__)
        else:
            return socket.recvfrom(self, *args)

    def recvfrom_into(self, *args):
        if self._sslobj:
            raise ValueError("recvfrom_into not allowed on instances of %s" % self.__class__)
        else:
            return socket.recvfrom_into(self, *args)

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
                    return b''
                elif ex.args[0] == SSL_ERROR_WANT_READ:
                    if self.timeout == 0.0:
                        raise
                    six.exc_clear()
                    self._io.wait_read(timeout=self.timeout, timeout_exc=_SSLErrorReadTimeout)
                elif ex.args[0] == SSL_ERROR_WANT_WRITE:
                    if self.timeout == 0.0:
                        raise
                    six.exc_clear()
                    self._io.wait_write(timeout=self.timeout, timeout_exc=_SSLErrorWriteTimeout)
                else:
                    raise

    def unwrap(self):
        if self._sslobj:
            s = self._sslobj_shutdown()
            self._sslobj = None
            return socket(_sock=s)
        else:
            raise ValueError("No SSL wrapper around " + str(self))

    def shutdown(self, how):
        self._sslobj = None
        socket.shutdown(self, how)

    def close(self):
        if self._makefile_refs < 1:
            self._sslobj = None
            socket.close(self)
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
                    six.exc_clear()
                    self._io.wait_read(timeout=self.timeout, timeout_exc=_SSLErrorHandshakeTimeout)
                elif ex.args[0] == SSL_ERROR_WANT_WRITE:
                    if self.timeout == 0.0:
                        raise
                    six.exc_clear()
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
        socket.connect(self, addr)
        if six.PY3:
            self._sslobj = self.context._wrap_socket(self._sock, False, self.server_hostname)
        else:
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
        newsock, addr = socket.accept(self)
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

    def makefile(self, mode='rwb', bufsize=-1):
        """Make and return a file-like object that
        works with the SSL connection.  Just use the code
        from the socket module."""
        self._makefile_refs += 1
        # close=True so as to decrement the reference count when done with
        # the file-like object.
        return _fileobject(self, mode, bufsize, close=True)


def wrap_socket(sock, *a, **kw):
    return SSLSocket(sock, *a, **kw)


if hasattr(__ssl__, 'sslwrap_simple'):
    def sslwrap_simple(sock, keyfile=None, certfile=None):
        """A replacement for the old socket.ssl function.  Designed
        for compability with Python 2.5 and earlier.  Will disappear in
        Python 3.0."""
        ssl_sock = SSLSocket(sock, keyfile=keyfile, certfile=certfile,
                             server_side=False,
                             cert_reqs=CERT_NONE,
                             ssl_version=PROTOCOL_SSLv23,
                             ca_certs=None)
        return ssl_sock
else:
    def sslwrap_simple(sock, keyfile=None, certfile=None):
        raise NotImplementedError

