
import functools
import pyuv

import eventlet


Null = object()

class Result(object):

    def __init__(self):
        self._g = None
        self._value = Null
        self._exc = Null
        self._done = False

    def set(self, value):
        assert not self._done, 'This Result has already been used'
        self._value = value
        if self._g is not None:
            eventlet.core.hub.next_tick(self._g.switch, self)

    def set_exception(self, typ, val, tb):
        assert not self._done, 'This Result has already been used'
        self._exc = (typ, val, tb)
        if self._g is not None:
            eventlet.core.hub.next_tick(self._g.switch, self)

    def get(self):
        assert not self._done, 'This Result has already been used'
        assert self._g is None, 'This Result is already used by %r' % self._g
        hub = eventlet.core.hub
        current = eventlet.core.current_greenlet
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
        result = Result()
        def after(value, error):
            if error is not None:
                result.set_exception(*error)
            else:
                result.set(value)
        self._tpool.queue_work(f, after)
        return result

