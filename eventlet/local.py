
import eventlet

__all__ = ['local']


def _get_local_dict():
    current = eventlet.core.current_greenlet
    s = '_%s__local_dict__' % current.__class__.__name__
    if not hasattr(current, s):
        setattr(current, s, {})
    return getattr(current, s)


class local(object):

    def __getattribute__(self, attr):
        local_dict = _get_local_dict()
        try:
            return local_dict[attr]
        except KeyError:
            raise AttributeError("'local' object has no attribute '%s'" % attr)

    def __setattr__(self, attr, value):
        local_dict = _get_local_dict()
        local_dict[attr] = value

    def __delattr__(self, attr):
        local_dict = _get_local_dict()
        try:
            del local_dict[attr]
        except KeyError:
            raise AttributeError(attr)

