#
# This file is part of flubber. See the NOTICE for more information.
#

from __future__ import absolute_import

from flubber import sleep
from flubber.patcher import slurp_properties

import time as __time__
__patched__ = ['sleep']

slurp_properties(__time__, globals(), ignore=__patched__, srckeys=dir(__time__))
del slurp_properties

