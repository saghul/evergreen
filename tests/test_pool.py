
from common import unittest, EvergreenTestCase

import evergreen
from evergreen.pool import Pool


class PoolTests(EvergreenTestCase):

    def test_pool(self):
        pool = Pool()
        def run(x):
            evergreen.sleep(x)
        def func():
            pool.spawn(run, 0.01)
            pool.spawn(run, 0.01)
            pool.spawn(run, 0.01)
            pool.join()
        evergreen.spawn(func)
        self.loop.run()


if __name__ == '__main__':
    unittest.main(verbosity=2)

