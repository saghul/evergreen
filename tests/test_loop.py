
from common import dummy, unittest, EvergreenTestCase

import evergreen
import signal
import threading
import time

from evergreen.six.moves import queue


class TLSTest(unittest.TestCase):

    def test_no_noop(self):
        loop = evergreen.current.loop
        self.assertTrue(loop)
        loop.destroy()
        self.assertRaises(RuntimeError, loop.destroy)

    def test_make_loop(self):
        loop = evergreen.EventLoop()
        self.assertTrue(evergreen.current.loop is loop)
        loop.destroy()

    def test_destroy_create(self):
        loop1 = evergreen.current.loop
        self.assertTrue(loop1)
        loop1.destroy()
        loop2 = evergreen.current.loop
        self.assertFalse(loop1 is loop2)
        loop2.destroy()

    def _start_loop(self, q):
        l = evergreen.loop.EventLoop()
        q.put(l)
        l.run_forever()
        l.destroy()

    def test_destroy(self):
        q = queue.Queue()
        thread = threading.Thread(target=self._start_loop, args=(q,))
        thread.start()

        loop = q.get()
        self.assertRaises(RuntimeError, loop.destroy)
        loop.call_from_thread(loop.stop)

        thread.join()


class LoopTests(EvergreenTestCase):

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

    def test_call_later_cancel2(self):
        d = dummy()
        d.called = False
        def func1():
            h2.cancel()
        def func2():
            d.called = True
        h1 =  self.loop.call_later(0.01, func1)
        h2 =  self.loop.call_later(0.01, func2)
        self.loop.run()
        self.assertFalse(d.called)

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
            self.assertNotEqual(r.get(), tid)
        evergreen.spawn(func)
        self.loop.run()

    def test_run_forever(self):
        d = dummy()
        d.called = False
        def stop_loop():
            d.called = True
            self.loop.stop()
        def func():
            import time
            time.sleep(0.2)
            self.loop.call_from_thread(stop_loop)
        t = threading.Thread(target=func)
        t.start()
        self.loop.run_forever()
        t.join()
        self.assertTrue(d.called)

    def test_signal(self):
        if not hasattr(signal, 'SIGALRM'):
            self.skipTest('No signal support')
            return
        d = dummy()
        d.called = False
        def signal_cb():
            d.called = True
        h = self.loop.add_signal_handler(signal.SIGALRM, signal_cb)
        signal.setitimer(signal.ITIMER_REAL, 0.1, 0)  # Send SIGALRM once
        self.loop.call_later(0.15, self.loop.stop)
        self.loop.run_forever()
        self.assertTrue(d.called)

    def test_signal_multi(self):
        if not hasattr(signal, 'SIGALRM'):
            self.skipTest('No signal support')
            return
        d = dummy()
        d.called1 = False
        d.called2 = False
        def signal_cb1():
            d.called1 = True
        def signal_cb2():
            d.called2 = True
        h1 = self.loop.add_signal_handler(signal.SIGALRM, signal_cb1)
        h2 = self.loop.add_signal_handler(signal.SIGALRM, signal_cb2)
        signal.setitimer(signal.ITIMER_REAL, 0.1, 0)  # Send SIGALRM once
        self.loop.call_later(0.15, self.loop.stop)
        self.loop.run_forever()
        self.assertTrue(d.called1)
        self.assertTrue(d.called2)

    def test_signal_cancel(self):
        if not hasattr(signal, 'SIGALRM'):
            self.skipTest('No signal support')
            return
        d = dummy()
        d.called1 = False
        d.called2 = False
        def signal_cb1():
            d.called1 = True
        def signal_cb2():
            d.called2 = True
        h1 = self.loop.add_signal_handler(signal.SIGALRM, signal_cb1)
        h2 = self.loop.add_signal_handler(signal.SIGALRM, signal_cb2)
        h2.cancel()
        signal.setitimer(signal.ITIMER_REAL, 0.1, 0)  # Send SIGALRM once
        self.loop.call_later(0.15, self.loop.stop)
        self.loop.run_forever()
        self.assertTrue(d.called1)
        self.assertFalse(d.called2)

    def test_signal_remove(self):
        if not hasattr(signal, 'SIGALRM'):
            self.skipTest('No signal support')
            return
        d = dummy()
        d.called1 = False
        d.called2 = False
        def signal_cb1():
            d.called1 = True
        def signal_cb2():
            d.called2 = True
        h1 = self.loop.add_signal_handler(signal.SIGALRM, signal_cb1)
        self.loop.remove_signal_handler(signal.SIGALRM)
        h2 = self.loop.add_signal_handler(signal.SIGALRM, signal_cb2)
        signal.setitimer(signal.ITIMER_REAL, 0.1, 0)  # Send SIGALRM once
        self.loop.call_later(0.15, self.loop.stop)
        self.loop.run_forever()
        self.assertFalse(d.called1)
        self.assertTrue(d.called2)

    def test_destroy_while_running(self):
        def func():
            evergreen.sleep(0.01)
            self.assertRaises(RuntimeError, self.loop.destroy)
        evergreen.spawn(func)
        self.loop.run()


if __name__ == '__main__':
    unittest.main(verbosity=2)

