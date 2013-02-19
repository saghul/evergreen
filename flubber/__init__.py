# -*- coding: utf-8 -
#
# This file is part of flubber. See the NOTICE for more information.

__version__ = '0.0.1.dev'

from flubber.hub import *
from flubber.tasks import *

__all__ = [hub.__all__ +
           tasks.__all__ +
           ['current', '__version__']]


class _CurrentContext(object):

    @property
    def hub(self):
        return get_hub()

    @property
    def task(self):
        return get_current()

current = _CurrentContext()

