#
# This file is part of Evergreen. See the NOTICE for more information.
#

__version__ = '0.0.4'

from evergreen.channel import *
from evergreen.tasks import *
from evergreen.core import *

__all__ = [channel.__all__ +
           tasks.__all__ +
           core.__all__ +
           ['current', '__version__']]


class _CurrentContext(object):

    @property
    def loop(self):
        return EventLoop.current()

    @property
    def task(self):
        return Task.current()

current = _CurrentContext()

