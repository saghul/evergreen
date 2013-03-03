
from common import unittest, FlubberTestCase

import flubber
from flubber.event import Event


class EventTests(FlubberTestCase):

    def test_event_simple(self):
        ev = Event()
        def waiter():
            self.assertTrue(ev.wait())
        flubber.spawn(waiter)
        flubber.spawn(ev.set)
        self.loop.run()

    def test_event_timeout(self):
        ev = Event()
        def waiter():
            self.assertFalse(ev.wait(0.001))
        flubber.spawn(waiter)
        self.loop.call_later(0.1, ev.set)
        self.loop.run()

    def test_event_kill_waiter(self):
        ev = Event()
        def waiter():
            ev.wait()
        t1 = flubber.spawn(waiter)
        flubber.spawn(t1.kill)
        flubber.spawn(ev.set)
        self.loop.run()
        self.assertTrue(ev.is_set())

    def test_event_clear(self):
        ev = Event()
        def waiter():
            self.assertTrue(ev.wait())
            ev.clear()
        flubber.spawn(waiter)
        flubber.spawn(ev.set)
        self.loop.run()
        self.assertFalse(ev.is_set())


if __name__ == '__main__':
    unittest.main(verbosity=2)

