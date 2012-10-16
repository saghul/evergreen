
import functools
import pyuv

from eventlet.support import greenlets as greenlet
#from eventlet.greenthread import getcurrent


Null = object()

class Result(object):

    def __init__(self, hub):
        self._g = None
        self._hub = hub
        self._value = Null
        self._exc = Null
        self._done = False

    def set(self, value):
        assert not self._done, 'This Result has already been used'
        self._value = value
        if self._g is not None:
            self._hub.schedule_call_global(0, self._g.switch, self)

    def set_exception(self, typ, val, tb):
        assert not self._done, 'This Result has already been used'
        self._exc = (typ, val, tb)
        if self._g is not None:
            self._hub.schedule_call_global(0, self._g.switch, self)

    def get(self):
        from eventlet.hub import get_hub
        assert not self._done, 'This Result has already been used'
        assert self._g is None, 'This Result is already used by %r' % self._g
        current = greenlet.getcurrent()
        hub = get_hub()
        assert current is not hub.greenlet, 'Cannot block in the Hub'
        self._g = current
        try:
            if self._exc is not Null:
                raise self._exc[0], self._exc[1], self._exc[2]
            elif self._value is not Null:
                return self._value
            else:
                result = hub.switch()
                assert result is self, 'Invalid switch into Result.get(), result: %r' % result
                if self._exc is not Null:
                    raise self._exc[0], self._exc[1], self._exc[2]
                elif self._value is not Null:
                    return self._value
                else:
                    return None
        finally:
            self._g = None
            self._hub = None
            self._value = None
            self._exc = None
            self._done = True


class ThreadPool(object):

    def __init__(self, hub):
        self._hub = hub
        self._tpool = pyuv.ThreadPool(self._hub.loop)

    def spawn(self, func, *args, **kwargs):
        f = functools.partial(func, *args, **kwargs)
        result = Result(self._hub)
        def after(value, error):
            if error is not None:
                result.set_exception(*error)
            else:
                result.set(value)
        self._tpool.queue_work(f, after)
        return result

