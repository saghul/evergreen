
from common import unittest, EvergreenTestCase

import evergreen
from evergreen.timeout import Timeout


class FooTimeout(Exception):
    pass


class TimeoutTests(EvergreenTestCase):

    def test_with_timeout(self):
        def sleep():
            with Timeout(0.01):
                evergreen.sleep(10)
        def func():
            self.assertRaises(Timeout, sleep)
        evergreen.spawn(func)
        self.loop.run()

    def test_with_none_timeout(self):
        def sleep():
            with Timeout(None):
                evergreen.sleep(0.01)
        def func():
            sleep()
        evergreen.spawn(func)
        self.loop.run()

    def test_with_negative_timeout(self):
        def sleep():
            with Timeout(-1):
                evergreen.sleep(0.01)
        def func():
            sleep()
        evergreen.spawn(func)
        self.loop.run()

    def test_timeout_custom_exception(self):
        def sleep():
            with Timeout(0.01, FooTimeout):
                evergreen.sleep(10)
        def func():
            self.assertRaises(FooTimeout, sleep)
        evergreen.spawn(func)
        self.loop.run()

    def test_timeout(self):
        def func():
            t = Timeout(0.01)
            t.start()
            try:
                evergreen.sleep(10)
            except Timeout as e:
                self.assertTrue(t is e)
        evergreen.spawn(func)
        self.loop.run()

