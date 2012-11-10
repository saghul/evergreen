
import functools
import pyuv

from eventlet.futures import Future


class ThreadPool(object):

    def __init__(self, hub):
        self._tpool = pyuv.ThreadPool(hub.loop)

    def spawn(self, func, *args, **kwargs):
        f = functools.partial(func, *args, **kwargs)
        result = Future()
        def after(value, error):
            if error is not None:
                result.set_exception(error)
            else:
                result.set_result(value)
        self._tpool.queue_work(f, after)
        return result

