# -*- coding: utf-8 -
#
# This file is part of flubber. See the NOTICE for more information.

import pyuv
import sys

from flubber.futures import Future

__all__ = ('ThreadPool')


class _Work(object):

    def __init__(self, future, func, *args, **kwargs):
        self.future = future
        self.func = func
        self.args = args
        self.kwargs = kwargs
        self.result = None
        self.exc = None

    def __call__(self):
        self.future.set_running_or_notify_cancel()
        try:
            self.result = self.func(*self.args, **self.kwargs)
        except:
            self.exc = sys.exc_info()


class _WorkFuture(Future):

    def __init__(self, work_request=None):
        super(_WorkFuture, self).__init__()
        self.work_request = work_request

    def canceli(self):
        if self.work_request:
            if not self.work_request.cancel():
                return False
        return super(_WorkFuture, self).cancel()


class ThreadPool(object):

    def __init__(self, hub):
        self._loop = hub.loop

    def spawn(self, func, *args, **kwargs):
        result = _WorkFuture()
        work = _Work(result, func, *args, **kwargs)
        def after(error):
            if error is not None:
                assert error == pyuv.errno.UV_ECANCELLED
                return
            if work.exc is not None:
                result.set_exception(work.exc)
            else:
                result.set_result(work.result)
        req = self._loop.queue_work(work, after)
        result.work_request = req
        return result

