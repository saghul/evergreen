# -*- coding: utf-8 -
#
# This file is part of flubber. See the NOTICE for more information.

from functools import partial

import flubber

from flubber.event import Event
from flubber.locks import Semaphore

__all__ = ['Pool']


class Pool(object):

    def __init__(self, size=1000):
        self._size = size
        self._lock = Semaphore(size)
        self._running_jobs = 0
        self._end_event = Event()
        self._end_event.set()

    def spawn(self, func, *args, **kw):
        self._lock.acquire()
        self._running_jobs += 1
        self._end_event.clear()
        flubber.spawn(self._runner, partial(func, *args, **kw))

    def join(self, timeout=None):
        self._end_event.wait(timeout)

    def _runner(self, func):
        try:
            func()
        finally:
            self._running_jobs -= 1
            if self._running_jobs == 0:
                self._end_event.set()
            self._lock.release()

    def __repr__(self):
        return '<%s(size=%d), %d running jobs>' % (self.__class__.__name__, self._size, self._running_jobs)

