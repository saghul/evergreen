#
# This file is part of flubber. See the NOTICE for more information.
#

import greenlet

__all__ = ['tasklet', 'get_current', 'TaskletExit']


tasklet = greenlet.greenlet
get_current = greenlet.getcurrent
TaskletExit = greenlet.GreenletExit

