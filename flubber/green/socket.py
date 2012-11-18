
import warnings

import flubber

__socket    = __import__('socket')
__all__     = __socket.__all__
__patched__ = ['fromfd', 'socketpair', 'ssl', 'socket', 'gethostbyname', 'gethostbyname_ex', 'getnameinfo', 'getaddrinfo', 'create_connection',]

from flubber.patcher import slurp_properties
slurp_properties(__socket, globals(), ignore=__patched__, srckeys=dir(__socket))

from flubber.io import GreenSocket as socket, _GLOBAL_DEFAULT_TIMEOUT, _fileobject


try:
    __original_fromfd__ = __socket.fromfd
    def fromfd(*args):
        return socket(__original_fromfd__(*args))
except AttributeError:
    pass


try:
    __original_socketpair__ = __socket.socketpair
    def socketpair(*args):
        one, two = __original_socketpair__(*args)
        return socket(one), socket(two)
except AttributeError:
    pass


try:
    from flubber.green import ssl as ssl_module
    sslerror = __socket.sslerror
    __socket.ssl
    def ssl(sock, certificate=None, private_key=None):
        warnings.warn("socket.ssl() is deprecated.  Use ssl.wrap_socket() instead.", DeprecationWarning, stacklevel=2)
        return ssl_module.sslwrap_simple(sock, private_key, certificate)
except AttributeError:
    # if the real socket module doesn't have the ssl method or sslerror
    # exception, we can't emulate them
    pass


def _run_in_threadpool(func, *args, **kw):
    hub = flubber.core.hub
    return hub.threadpool.spawn(func, *args, **kw)


def gethostbyname(*args, **kw):
    return _run_in_threadpool(__socket.gethostbyname, *args, **kw).result()


def gethostbyname_ex(*args, **kw):
    return _run_in_threadpool(__socket.gethostbyname_ex, *args, **kw).result()


def getnameinfo(*args, **kw):
    return _run_in_threadpool(__socket.getnameinfo, *args, **kw).result()


def getaddrinfo(*args, **kw):
    return _run_in_threadpool(__socket.getaddrinfo, *args, **kw).result()


def create_connection(address, timeout=_GLOBAL_DEFAULT_TIMEOUT, source_address=None):
    """Connect to *address* and return the socket object.

    Convenience function.  Connect to *address* (a 2-tuple ``(host,
    port)``) and return the socket object.  Passing the optional
    *timeout* parameter will set the timeout on the socket instance
    before attempting to connect.  If no *timeout* is supplied, the
    global default timeout setting returned by :func:`getdefaulttimeout`
    is used.
    """

    msg = "getaddrinfo returns an empty list"
    host, port = address
    for res in getaddrinfo(host, port, 0, SOCK_STREAM):
        af, socktype, proto, canonname, sa = res
        sock = None
        try:
            sock = socket(af, socktype, proto)
            if timeout is not _GLOBAL_DEFAULT_TIMEOUT:
                sock.settimeout(timeout)
            if source_address:
                sock.bind(source_address)
            sock.connect(sa)
            return sock
        except error, msg:
            if sock is not None:
                sock.close()
    raise error, msg

