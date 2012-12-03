# -*- coding: utf-8 -
#
# This file is part of flubber. See the NOTICE for more information.

__all__ = ['Event']

import flubber

from flubber.timeout import Timeout


class Event(object):

    def __init__(self):
        self._flag = False
        self._waiters = set()

    def is_set(self):
        return self._flag

    def set(self):
        self._flag = True
        if self._waiters:
            flubber.current.hub.next_tick(self._notify_waiters)

    def clear(self):
        self._flag = False

    def wait(self, timeout=None):
        if self._flag:
            return True
        current = flubber.current.task
        hub = flubber.current.hub
        self._waiters.add(current)
        timer = Timeout(timeout)
        timer.start()
        try:
            try:
                hub.switch()
            except Timeout as e:
                if e is not timer:
                    raise
        finally:
            timer.cancel()
            self._waiters.remove(current)
        return self._flag

    def _notify_waiters(self):
        to_notify = set(self._waiters)
        while to_notify:
            waiter = to_notify.pop()
            if waiter in self._waiters:
                waiter.switch()

