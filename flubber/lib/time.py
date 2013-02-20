# -*- coding: utf-8 -
#
# This file is part of flubber. See the NOTICE for more information.

from flubber import sleep
from flubber.patcher import slurp_properties

__time = __import__('time')
__patched__ = ['sleep']

slurp_properties(__time, globals(), ignore=__patched__, srckeys=dir(__time))

