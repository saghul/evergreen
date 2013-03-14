#
# This file is part of flubber. See the NOTICE for more information.
#

import errno
import pyuv
import six

from collections import deque
from flubber.event import Event

__all__ = ['ReadBuffer', 'Result', 'convert_errno']


class ReadBuffer(object):

    def __init__(self, max_size=100*1024*1024):
        self._max_size = max_size
        self._buf = deque()
        self._size = 0
        self._closed = False

    @property
    def closed(self):
        return self._closed

    def read(self, nbytes):
        self._check_closed()
        if self._size >= nbytes:
            return self._consume(nbytes)
        return None

    def read_until(self, delimiter):
        # Multi-byte delimiters (e.g. '\r\n') may straddle two
        # chunks in the read buffer, so we can't easily find them
        # without collapsing the buffer. However, since protocols
        # using delimited reads (as opposed to reads of a known
        # length) tend to be "line" oriented, the delimiter is likely
        # to be in the first few chunks. Merge the buffer gradually
        # since large merges are relatively expensive and get undone in
        # consume().
        self._check_closed()
        if self._buf:
            while True:
                loc = self._buf[0].find(delimiter)
                if loc != -1:
                    delimiter_len = len(delimiter)
                    return self._consume(loc + delimiter_len)
                if len(self._buf) == 1:
                    break
                self._double_prefix()
        return None

    def read_until_regex(self, regex):
        # regex must be a compiled re object
        self._check_closed()
        if self._buf:
            while True:
                m = regex.search(self._buf[0])
                if m is not None:
                    return self._consume(m.end())
                if len(self._buf) == 1:
                    break
                self._double_prefix()
        return None

    def feed(self, chunk):
        self._check_closed()
        self._buf.append(chunk)
        self._size += len(chunk)
        if self._size >= self._max_size:
            self.close()
            raise IOError('Maximum buffer size reached')

    def close(self):
        if not self._closed:
            self._closed = True
            del self._buf, self._size

    # internal

    def _check_closed(self):
        if self._closed:
            raise ValueError('I/O operation on closed buffer')

    def _consume(self, loc):
        if loc == 0:
            return b''
        self._merge_prefix(loc)
        self._size -= loc
        return self._buf.popleft()

    def _double_prefix(self):
        """Grow the given deque by doubling, but don't split the second chunk just
        because the first one is small.
        """
        new_len = max(len(self._buf[0]) * 2, (len(self._buf[0]) + len(self._buf[1])))
        self._merge_prefix(new_len)

    def _merge_prefix(self, size):
        """Replace the first entries in a deque of strings with a single
        string of up to size bytes.

        >>> d = collections.deque(['abc', 'de', 'fghi', 'j'])
        >>> _merge_prefix(d, 5); print(d)
        deque(['abcde', 'fghi', 'j'])

        Strings will be split as necessary to reach the desired size.
        >>> _merge_prefix(d, 7); print(d)
        deque(['abcdefg', 'hi', 'j'])

        >>> _merge_prefix(d, 3); print(d)
        deque(['abc', 'defg', 'hi', 'j'])

        >>> _merge_prefix(d, 100); print(d)
        deque(['abcdefghij'])
        """
        if len(self._buf) == 1 and len(self._buf[0]) <= size:
            return
        prefix = []
        remaining = size
        while self._buf and remaining > 0:
            chunk = self._buf.popleft()
            if len(chunk) > remaining:
                self._buf.appendleft(chunk[remaining:])
                chunk = chunk[:remaining]
            prefix.append(chunk)
            remaining -= len(chunk)
        if prefix:
            self._buf.appendleft(b''.join(prefix))
        if not self._buf:
            self._buf.appendleft(b'')


class Result(object):

    def __init__(self):
        self._event = Event()
        self._result = None
        self._exception = None
        self._used = False

    def is_set(self):
        return self._event.is_set()

    def set_result(self, value):
        if self.is_set():
            raise RuntimeError('already set')
        self._result = value
        self._event.set()

    def set_exception(self, exc):
        if self.is_set():
            raise RuntimeError('already set')
        self._exception = exc
        self._event.set()

    def wait(self, timeout=None):
        if self._used:
            raise RuntimeError('already used, clear it in order to use it again')
        self._event.wait(timeout)
        try:
            if self.is_set():
                return self._get_result()
            return None
        finally:
            self._result = self._exception = None

    def clear(self):
        self._event.clear()
        self._result = None
        self._exception = None
        self._used = False

    def _get_result(self):
        self._used = True
        if self._exception is not None:
            six.reraise(type(self._exception), self._exception)
        else:
            return self._result


def convert_errno(errorno):
    # Convert 2 -> UV_EADDRINFO -> EADDRINFO -> (code for EADDRINFO)
    code = pyuv.errno.errorcode[errorno][3:]
    return getattr(errno, code, -1)

