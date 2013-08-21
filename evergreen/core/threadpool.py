#
# This file is part of Evergreen. See the NOTICE for more information.
#

import pyuv
import sys

from evergreen.event import Event
from evergreen.futures import Future

__all__ = ('ThreadPool')

"""Internal thread pool which uses the pyuv work queuing capability. This module
is for internal use of Evergreen.
"""


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
        self = None


class ThreadPool(object):

    def __init__(self, loop):
        self.loop = loop

    def spawn(self, func, *args, **kwargs):
        fut = Future()
        work = _Work(func, *args, **kwargs)
        def after(error):
            if error is not None:
                assert error == pyuv.errno.UV_ECANCELLED
                return
            if work.exc is not None:
                fut.set_exception(work.exc)
            else:
                fut.set_result(work.result)
        fut.set_running_or_notify_cancel()
        self.loop._loop.queue_work(work, after)
        return fut

