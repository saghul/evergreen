
import eventlet

from collections import deque


class Bomb(object):

    def __init__(self, exp_type=None, exp_value=None, exp_traceback=None):
        self.type = exp_type
        self.value = exp_value
        self.traceback = exp_traceback

    def raise_(self):
        # TODO: use six.reraise
        raise self.type, self.type(self.value), self.traceback


class Channel(object):

    def __init__(self, max_size=0):
        self.max_size = max_size
        self.items = deque()
        self._waiters = set()
        self._senders = set()

    def __nonzero__(self):
        return len(self.items) > 0

    def __len__(self):
        return len(self.items)

    def __repr__(self):
        params = (self.__class__.__name__, hex(id(self)), self.max_size, len(self.items),
                  len(self._waiters), len(self._senders))
        return '<%s at %s max=%s items[%d] _w[%s] _s[%s]>' % params

    def send(self, value):
        current = eventlet.core.current_greenlet
        hub = eventlet.core.hub
        assert hub.greenlet is not current, 'do not call blocking functions from the mainloop'
        self.items.append(value)
        if self._waiters:
            hub.next_tick(self._do_switch)
        if len(self.items) > self.max_size:
            self._senders.add(current)
            try:
                eventlet.suspend(switch_back=False)
            finally:
                self._senders.discard(current)

    def send_exception(self, exc_type=None, exc_value=None, exc_tb=None):
        self.send(Bomb(exc_type, exc_value, exc_tb))

    def wait(self):
        # TODO: add timeout argument
        current = eventlet.core.current_greenlet
        hub = eventlet.core.hub
        if self.items:
            value = self.items.popleft()
            if len(self.items) <= self.max_size:
                hub.next_tick(self._do_switch)
            if isinstance(value, Bomb):
                value.raise_()
                return
            else:
                return value
        else:
            if self._senders:
                hub.next_tick(self._do_switch)
            self._waiters.add(current)
            try:
                value = eventlet.suspend(switch_back=False)
                if isinstance(value, Bomb):
                    value.raise_()
                    return
                else:
                    return value
            finally:
                self._waiters.discard(current)

    def _do_switch(self):
        while True:
            if self._waiters and self.items:
                waiter = self._waiters.pop()
                value = self.items.popleft()
                waiter.switch(value)
            elif self._senders and len(self.items) <= self.max_size:
                sender = self._senders.pop()
                sender.switch()
            else:
                break

