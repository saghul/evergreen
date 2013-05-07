#
# This file is part of Evergreen. See the NOTICE for more information.
#

__version__ = '0.0.2'

from evergreen.channel import *
from evergreen.loop import *
from evergreen.tasks import *

__all__ = [channel.__all__ +
           loop.__all__ +
           tasks.__all__ +
           ['current', '__version__']]


class _CurrentContext(object):

    @property
    def loop(self):
        return loop.get_loop()

    @property
    def task(self):
        return tasks.get_current()

current = _CurrentContext()

