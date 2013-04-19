#
# This file is part of Evergreen. See the NOTICE for more information.
#

import pyuv
import sys

from evergreen.event import Event

__all__ = ('ThreadPool')


class _Work(object):
    __slots__ = ('func', 'args', 'kwargs', 'result', 'exc')

    def __init__(self, func, *args, **kwargs):
        self.func = func
        self.args = args
        self.kwargs = kwargs
        self.result = None
        self.exc = None

    def __call__(self):
        try:
            self.result = self.func(*self.args, **self.kwargs)
        except BaseException:
            self.exc = sys.exc_info()


class _Result(object):

    def __init__(self):
        self._result = None
        self._exc = None
        self._event = Event()
        self._used = False

    def wait(self):
        if self._used:
            raise RuntimeError('result object already used')
        try:
            self._event.wait()
            if self._exc is not None:
                raise self._exc
            else:
                return self._result
        finally:
            self._used = True
            self._result = None
            self._exc = None

    def _set_result(self, result):
        self._result = result
        self._event.set()

    def _set_exception(self, exc):
        self._exc = exc
        self._event.set()


class ThreadPool(object):

    def __init__(self, loop):
        self.loop = loop

    def spawn(self, func, *args, **kwargs):
        result = _Result()
        work = _Work(func, *args, **kwargs)
        def after(error):
            if error is not None:
                assert error == pyuv.errno.UV_ECANCELLED
                return
            if work.exc is not None:
                result._set_exception(work.exc)
            else:
                result._set_result(work.result)
        req = self.loop._loop.queue_work(work, after)
        return result

