
from common import dummy, unittest, FlubberTestCase

import flubber
import threading
import time


class TLSTest(unittest.TestCase):

    def test_no_noop(self):
        self.assertRaises(RuntimeError, lambda: flubber.current.loop)

    def test_make_loop(self):
        loop = flubber.EventLoop()
        self.assertTrue(flubber.current.loop is loop)
        loop._destroy()
        self.assertRaises(RuntimeError, lambda: flubber.current.loop)


class LoopTests(FlubberTestCase):

    def test_run(self):
        self.loop.run()
        self.assertTrue(self.loop.tasklet.dead)

    def test_call_soon(self):
        d = dummy()
        d.called = False
        def func():
            d.called = True
        self.loop.call_soon(func)
        self.loop.run()
        self.assertTrue(d.called)

    def test_call_soon_cancel(self):
        d = dummy()
        d.called = False
        def func():
            d.called = True
        h =  self.loop.call_soon(func)
        h.cancel()
        self.loop.run()
        self.assertFalse(d.called)

    def test_call_later(self):
        d = dummy()
        d.called = False
        def func():
            d.called = True
        self.loop.call_later(0.1, func)
        self.loop.run()
        self.assertTrue(d.called)

    def test_call_later_cancel(self):
        d = dummy()
        d.called = False
        def func():
            d.called = True
        h =  self.loop.call_later(0.1, func)
        h.cancel()
        self.loop.run()
        self.assertFalse(d.called)

    def test_call_repeatedly(self):
        d = dummy()
        d.counter = 0
        d.handler = None
        def func():
            d.counter += 1
            if d.counter == 3:
                d.handler.cancel()
        d.handler = self.loop.call_repeatedly(0.1, func)
        self.loop.run()
        self.assertEqual(d.counter, 3)

    def test_stop(self):
        self.assertRaises(RuntimeError, self.loop.stop)

    def test_stop2(self):
        self.loop.call_later(100, lambda: None)
        self.loop.call_later(0.01, self.loop.stop)
        t0 = time.time()
        self.loop.run()
        t1 = time.time()
        self.assertTrue(0 <= t1-t0 < 0.1)

    def test_internal_threadpool(self):
        tid = threading.current_thread().ident
        def runner():
            import time
            time.sleep(0.001)
            return threading.current_thread().ident
        def func():
            r = self.loop._threadpool.spawn(runner)
            self.assertNotEqual(r.wait(), tid)
        flubber.spawn(func)
        self.loop.run()


if __name__ == '__main__':
    unittest.main(verbosity=2)

