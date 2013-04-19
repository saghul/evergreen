#
# This file is part of Evergreen. See the NOTICE for more information.
#

from evergreen import patcher
socket = patcher.original('socket')

__all__ = ('SocketPair')


try:
    from socket import socketpair
except ImportError:
    def socketpair(family=socket.AF_INET, type=socket.SOCK_STREAM, proto=0):
        """Emulate the Unix socketpair() function on Windows."""
        # We create a connected TCP socket. Note the trick with setblocking(0)
        # that prevents us from having to create a thread.
        lsock = socket.socket(family, type, proto)
        lsock.bind(('localhost', 0))
        lsock.listen(1)
        addr, port = lsock.getsockname()
        csock = socket.socket(family, type, proto)
        csock.setblocking(False)
        try:
            csock.connect((addr, port))
        except socket.error as e:
            if e.errno != errno.WSAEWOULDBLOCK:
                lsock.close()
                csock.close()
                raise
        ssock, _ = lsock.accept()
        csock.setblocking(True)
        lsock.close()
        return (ssock, csock)


class SocketPair(object):

    def __init__(self):
        self._reader, self._writer = socketpair()
        self._reader.setblocking(False)
        self._writer.setblocking(False)

    def reader_fileno(self):
        return self._reader.fileno()

    def writer_fileno(self):
        return self._writer.fileno()

    def close(self):
        self._reader.close()
        self._writer.close()

