
from common import unittest, FlubberTestCase

import flubber
from flubber.pool import Pool


class PoolTests(FlubberTestCase):

    def test_pool(self):
        pool = Pool()
        def run(x):
            flubber.sleep(x)
        def func():
            pool.spawn(run, 0.01)
            pool.spawn(run, 0.01)
            pool.spawn(run, 0.01)
            pool.join()
        flubber.spawn(func)
        self.loop.run()

