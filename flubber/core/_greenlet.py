
import greenlet as g

__all__ = ['greenlet', 'get_current', 'GreenletExit']


greenlet = g.greenlet
get_current = g.getcurrent
GreenletExit = g.GreenletExit

