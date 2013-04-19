
from common import unittest, EvergreenTestCase

import evergreen
from evergreen.local import local


class LocalTests(EvergreenTestCase):

    def test_local(self):
        tls = local()
        tls.foo = 42
        def func(x):
            self.assertRaises(AttributeError, lambda: tls.foo)
            tls.foo = x
            self.assertEqual(tls.foo, x)
        evergreen.spawn(func, 1)
        evergreen.spawn(func, 2)
        evergreen.spawn(func, 3)
        self.loop.run()


if __name__ == '__main__':
    unittest.main(verbosity=2)

