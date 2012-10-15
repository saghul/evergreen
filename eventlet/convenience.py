import sys

from eventlet.green import socket


def _check_ip_family(family, address):
    try:
        socket.inet_pton(family, address)
    except socket.error:
        return False
    return True

def is_ipv4(address):
    return _check_ip_family(socket.AF_INET, address)

def is_ipv6(address):
    return _check_ip_family(socket.AF_INET6, address)


def connect(endpoint, source_address=None):
    """Convenience function for opening client sockets.

    :param endpoint: Endpoint address to connect to. TCP, UDP and UNIX sockets are supported. Examples:
        tcp:127.0.0.1:1234
        udp:127.0.0.1:1234
        unix:/tmp/foo.sock
    :param source_address: Local address to bind to, optional.
    :return: The connected green socket object.
    """

    proto, _, netloc = endpoint.partition(':')
    proto = proto.lower()
    if proto in ('tcp', 'udp'):
        host, port = netloc.split(':')
        if not port.isdigit():
            raise ValueError('invalid port specified: %s' % port)
        err = None
        sock_type = socket.SOCK_STREAM if proto=='tcp' else socket.SOCK_DGRAM
        for res in socket.getaddrinfo(host, port, 0, sock_type):
            af, socktype, proto, canonname, sa = res
            sock = None
            try:
                sock = socket.socket(af, socktype, proto)
                if source_address:
                    sock.bind(source_address)
                sock.connect(sa)
                return sock
            except socket.error as _:
                err = _
                if sock is not None:
                    sock.close()
        if err is not None:
            raise err
        else:
            raise socket.error("getaddrinfo returns an empty list")
    elif proto == 'unix':
        addr = netloc
        sock = socket.socket(socket.AF_UNIX)
        sock.connect(addr)
        return sock
    else:
        raise ValueError('invalid endpoint protocol specified: %s' % proto)


def listen(endpoint, backlog=128):
    """Convenience function for opening server sockets.  This
    socket can be used in :func:`~eventlet.serve` or a custom ``accept()`` loop.

    Sets SO_REUSEADDR on the socket to save on annoyance.

    :param endpoint: Endpoint address to listen on. TCP, UDP and UNIX sockets are supported. Examples:
        tcp:127.0.0.1:1234
        udp:127.0.0.1:1234
        unix:/tmp/foo.sock
    :param backlog: The maximum number of queued connections. Should be at least 1; the maximum value is system-dependent.
    :return: The listening green socket object.
    """

    proto, _, netloc = endpoint.partition(':')
    proto = proto.lower()
    if proto in ('tcp', 'udp'):
        addr, port = netloc.split(':')
        if not port.isdigit():
            raise ValueError('invalid port specified: %s' % port)
        socktype = socket.SOCK_STREAM if proto=='tcp' else socket.SOCK_DGRAM
        if is_ipv4(addr):
            sock = socket.socket(socket.AF_INET, socktype)
        elif is_ipv6(addr):
            sock = socket.socket(socket.AF_INET6, socktype)
        else:
            sock = socket.socket(socket.AF_INET, socktype)
        if sys.platform[:3] != "win":
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((addr, int(port)))
    elif proto == 'unix':
        addr = netloc
        sock = socket.socket(socket.AF_UNIX)
        sock.bind(addr)
    else:
        raise ValueError('invalid endpoint protocol specified: %s' % proto)
    sock.listen(backlog)
    return sock

