
from common import unittest, FlubberTestCase

import flubber
from flubber.local import local


class LocalTests(FlubberTestCase):

    def test_local(self):
        tls = local()
        tls.foo = 42
        def func(x):
            self.assertRaises(AttributeError, lambda: tls.foo)
            tls.foo = x
            self.assertEqual(tls.foo, x)
        flubber.spawn(func, 1)
        flubber.spawn(func, 2)
        flubber.spawn(func, 3)
        self.loop.run()


if __name__ == '__main__':
    unittest.main(verbosity=2)

