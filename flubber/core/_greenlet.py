# -*- coding: utf-8 -
#
# This file is part of flubber. See the NOTICE for more information.

import greenlet as g

__all__ = ['greenlet', 'get_current', 'GreenletExit']


greenlet = g.greenlet
get_current = g.getcurrent
GreenletExit = g.GreenletExit

