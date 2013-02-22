# -*- coding: utf-8 -
#
# This file is part of flubber. See the NOTICE for more information.

__version__ = '0.0.1.dev'

from flubber.loop import *
from flubber.tasks import *

__all__ = [loop.__all__ +
           tasks.__all__ +
           ['current', '__version__']]


class _CurrentContext(object):

    @property
    def loop(self):
        return get_loop()

    @property
    def task(self):
        return get_current()

current = _CurrentContext()

