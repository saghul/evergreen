#
# This file is part of Evergreen. See the NOTICE for more information.
#

import sys

from evergreen.lib import socket

__all__ = ['connect', 'listen']


def _check_ip_family(address, family):
    try:
        socket.inet_pton(family, address)
    except socket.error:
        return False
    return True


def connect(endpoint, timeout=socket._GLOBAL_DEFAULT_TIMEOUT, source_address=None):
    proto, _, netloc = endpoint.partition(':')
    proto = proto.lower()
    if proto in ('tcp', 'udp'):
        host, port = netloc.split(':')
        if not port.isdigit():
            raise ValueError('invalid port specified: %s' % port)
        return socket.create_connection((host, port), timeout, source_address)
    elif proto == 'unix':
        addr = netloc
        sock = socket.socket(socket.AF_UNIX)
        sock.connect(addr)
        return sock
    else:
        raise ValueError('invalid endpoint protocol specified: %s' % proto)


def listen(endpoint, backlog=128):
    proto, _, netloc = endpoint.partition(':')
    proto = proto.lower()
    if proto in ('tcp', 'udp'):
        addr, port = netloc.split(':')
        if not port.isdigit():
            raise ValueError('invalid port specified: %s' % port)
        socktype = socket.SOCK_STREAM if proto=='tcp' else socket.SOCK_DGRAM
        if _check_ip_family(addr, socket.AF_INET):
            sock = socket.socket(socket.AF_INET, socktype)
        elif _check_ip_family(addr, socket.AF_INET6):
            sock = socket.socket(socket.AF_INET6, socktype)
        else:
            raise RuntimeError('invalid address specified: %s' % addr)
        if sys.platform == 'win32':
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

