# -*- coding: utf-8 -
#
# This file is part of flubber. See the NOTICE for more information.

import functools
import pyuv

from flubber.futures import Future


class ThreadPool(object):

    def __init__(self, hub):
        self._loop = hub.loop

    def spawn(self, func, *args, **kwargs):
        f = functools.partial(func, *args, **kwargs)
        result = Future()
        def after(value, error):
            if error is not None:
                result.set_exception(error)
            else:
                result.set_result(value)
        self._loop.queue_work(f, after)
        return result

