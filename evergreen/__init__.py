#
# This file is part of Evergreen. See the NOTICE for more information.
#

__version__ = '0.0.3'

from evergreen.channel import *
from evergreen.tasks import *
from evergreen.core import loop, EventLoop

__all__ = [channel.__all__ +
           tasks.__all__ +
           ['EventLoop', 'current', '__version__']]


class _CurrentContext(object):

    @property
    def loop(self):
        return loop.get_loop()

    @property
    def task(self):
        return tasks.get_current()

current = _CurrentContext()

