
__all__ = ['Event']

import eventlet

from eventlet.timeout import Timeout


class Event(object):

    def __init__(self):
        self._flag = False
        self._waiters = set()
        self._notifier = None

    def is_set(self):
        return self._flag

    def set(self):
        self._flag = True
        if self._notifier is None:
            self._notifier = object()
            eventlet.core.hub.next_tick(self._notify_waiters)

    def clear(self):
        self._flag = False

    def wait(self, timeout=None):
        if self._flag:
            return True
        current = eventlet.core.current_greenlet
        hub = eventlet.core.hub
        assert current is not hub.greenlet, 'Cannot block in the main loop'
        self._waiters.add(current)
        if timeout is not None:
            t = Timeout(timeout)
            t.start()
        try:
            try:
                result = hub.switch()
                assert result is self, 'Invalid switch into Event.wait(): %r' % (result, )
            except Timeout as e:
                if e is not t:
                    raise
        finally:
            if timeout is not None:
                t.cancel()
            self._waiters.remove(current)
        return self._flag

    def _notify_waiters(self):
        to_notify = set(self._waiters)
        while to_notify:
            waiter = to_notify.pop()
            if waiter in self._waiters:
                waiter.switch(self)

