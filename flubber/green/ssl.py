
__ssl = __import__('ssl')
__patched__ = ['SSLSocket', 'wrap_socket', 'sslwrap_simple']

from flubber.patcher import slurp_properties
slurp_properties(__ssl, globals(), ignore=__patched__, srckeys=dir(__ssl))

from flubber.io import SSLSocket


def wrap_socket(sock, *a, **kw):
    return SSLSocket(sock, *a, **kw)


if hasattr(__ssl, 'sslwrap_simple'):
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

