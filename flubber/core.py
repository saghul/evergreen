
import sys
import types


class CoreModule(types.ModuleType):

    def __init__(self, name, dynamic_attributes):
        super(CoreModule, self).__init__(name)
        self.__dynamic_attributes = dynamic_attributes

    def __getattr__(self, name):
        func = self.__dynamic_attributes.get(name)
        if func is not None and callable(func):
            return func()
        raise AttributeError("'module' object has no attribute '%s'" % name)


def setup():
    from flubber.hub import get_hub
    from greenlet import getcurrent
    dynamic_attributes = {'hub': get_hub, 'current_greenlet': getcurrent}
    module = CoreModule(__name__, dynamic_attributes)
    sys.modules[__name__] = module
    return module

