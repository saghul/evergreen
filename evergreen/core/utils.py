#
# This file is part of Evergreen. See the NOTICE for more information.
#

from evergreen.locks import Condition, Lock

__all__ = ['Result']


Null = object()

class Result(object):
    """
    Result is an internal object which is meant to be used like a Future, but being more
    lightweight and supporting a single waiter. Example:

    result = Result()

    def f1():
        with result:
            some_async_func()
            return result.get()

    def some_async_func():
        # this function runs in a different task
        ...
        result.set_value(42)
    """

    __slots__ = ['_lock', '_cond', '_locked', '_used', '_exc', '_value']

    def __init__(self):
        self._lock = Lock()
        self._cond = Condition(Lock())
        self._locked = False
        self._used = False
        self._exc = self._value = Null

    def acquire(self):
        self._lock.acquire()
        self._locked = True

    def release(self):
        self._lock.release()
        self._locked = False
        self._used = False
        self._exc = self._value = Null

    def get(self):
        assert self._locked
        assert not self._used
        try:
            with self._cond:
                if self._exc == self._value == Null:
                    self._cond.wait()
            if self._exc != Null:
                raise self._exc
            assert self._value != Null
            return self._value
        finally:
            self._used = True
            self._exc = self._value = Null

    def set_value(self, value):
        assert self._locked
        assert not self._used
        assert self._exc == self._value == Null
        with self._cond:
            self._value = value
            self._cond.notify_all()

    def set_exception(self, value):
        assert self._locked
        assert not self._used
        assert self._exc == self._value == Null
        with self._cond:
            self._exc = value
            self._cond.notify_all()

    def __enter__(self):
        self.acquire()

    def __exit__(self, typ, val, tb):
        self.release()

