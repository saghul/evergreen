#
# This file is part of Evergreen. See the NOTICE for more information.
#

import pyuv


errorcode = {}
strerror = pyuv.errno.strerror

def _bootstrap():
    g = globals()
    for k, v in pyuv.errno.errorcode.items():
        e = v[3:]
        errorcode[k] = e
        g[e] = k
_bootstrap()
del _bootstrap, pyuv

