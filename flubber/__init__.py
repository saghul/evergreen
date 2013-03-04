#
# This file is part of flubber. See the NOTICE for more information.
#

__version__ = '0.0.1.dev'

from flubber.channel import *
from flubber.loop import *
from flubber.tasks import *

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

