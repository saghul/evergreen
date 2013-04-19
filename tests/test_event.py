
from common import unittest, EvergreenTestCase

import evergreen
from evergreen.event import Event


class EventTests(EvergreenTestCase):

    def test_event_simple(self):
        ev = Event()
        def waiter():
            self.assertTrue(ev.wait())
        evergreen.spawn(waiter)
        evergreen.spawn(ev.set)
        self.loop.run()

    def test_event_timeout(self):
        ev = Event()
        def waiter():
            self.assertFalse(ev.wait(0.001))
        evergreen.spawn(waiter)
        self.loop.call_later(0.1, ev.set)
        self.loop.run()

    def test_event_kill_waiter(self):
        ev = Event()
        def waiter():
            ev.wait()
        t1 = evergreen.spawn(waiter)
        evergreen.spawn(t1.kill)
        evergreen.spawn(ev.set)
        self.loop.run()
        self.assertTrue(ev.is_set())

    def test_event_clear(self):
        ev = Event()
        def waiter():
            self.assertTrue(ev.wait())
            ev.clear()
        evergreen.spawn(waiter)
        evergreen.spawn(ev.set)
        self.loop.run()
        self.assertFalse(ev.is_set())


if __name__ == '__main__':
    unittest.main(verbosity=2)

