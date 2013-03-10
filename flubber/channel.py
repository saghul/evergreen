#
# This file is part of flubber. See the NOTICE for more information.
#

from flubber import six
from flubber.event import Event
from flubber.locks import Semaphore

__all__ = ['Channel']


class _Bomb(object):

    def __init__(self, exp_type, exp_value=None, exp_traceback=None):
        self.type = exp_type
        self.value = exp_value if exp_value is not None else exp_type()
        self.traceback = exp_traceback

    def raise_(self):
        six.reraise(self.type, self.value, self.traceback)


class Channel(object):

    def __init__(self):
        self._send_lock = Semaphore(1)
        self._recv_lock = Semaphore(1)
        self._new_data = Event()
        self._recv_data = Event()
        self._data = None

    def send(self, data):
        with self._send_lock:
            self._data = data
            self._new_data.set()
            self._recv_data.wait()
            self._recv_data.clear()

    def send_exception(self, exc_type, exc_value=None, exc_tb=None):
        self.send(_Bomb(exc_type, exc_value, exc_tb))

    def receive(self):
        with self._recv_lock:
            self._new_data.wait()
            data, self._data = self._data, None
            self._new_data.clear()
            self._recv_data.set()
        if isinstance(data, _Bomb):
            data.raise_()
        else:
            return data

    def __iter__(self):
        return self

    def next(self):
        return self.receive()

    if six.PY3:
        __next__ = next
        del next

