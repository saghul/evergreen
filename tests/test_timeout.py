
from common import unittest, FlubberTestCase

import flubber
from flubber.timeout import Timeout


class FooTimeout(Exception):
    pass


class TimeoutTests(FlubberTestCase):

    def test_with_timeout(self):
        def sleep():
            with Timeout(0.01):
                flubber.sleep(10)
        def func():
            self.assertRaises(Timeout, sleep)
        flubber.spawn(func)
        self.loop.run()

    def test_with_none_timeout(self):
        def sleep():
            with Timeout(None):
                flubber.sleep(0.01)
        def func():
            sleep()
        flubber.spawn(func)
        self.loop.run()

    def test_with_negative_timeout(self):
        def sleep():
            with Timeout(-1):
                flubber.sleep(0.01)
        def func():
            sleep()
        flubber.spawn(func)
        self.loop.run()

    def test_timeout_custom_exception(self):
        def sleep():
            with Timeout(0.01, FooTimeout):
                flubber.sleep(10)
        def func():
            self.assertRaises(FooTimeout, sleep)
        flubber.spawn(func)
        self.loop.run()

    def test_timeout(self):
        def func():
            t = Timeout(0.01)
            t.start()
            try:
                flubber.sleep(10)
            except Timeout as e:
                self.assertTrue(t is e)
        flubber.spawn(func)
        self.loop.run()

