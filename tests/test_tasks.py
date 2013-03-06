
from common import dummy, unittest, FlubberTestCase

import flubber
import time


class MyTask(flubber.Task):
    called = False

    def run_(self):
        self.called = True


class TasksTests(FlubberTestCase):

    def test_simple_task(self):
        d = dummy()
        d.called = False
        def func():
            d.called = True
        task = flubber.Task(target=func)
        task.start()
        self.loop.run()
        self.assertTrue(d.called)

    def test_spawn(self):
        d = dummy()
        d.called = False
        def func():
            d.called = True
        flubber.spawn(func)
        self.loop.run()
        self.assertTrue(d.called)

    def test_spawn_kill(self):
        d = dummy()
        d.called = False
        def func():
            d.called = True
        task = flubber.spawn(func)
        task.kill()
        self.loop.run()
        self.assertFalse(d.called)

    def test_task_decorator(self):
        d = dummy()
        d.called = False
        @flubber.task
        def func():
            d.called = True
        func()
        self.loop.run()
        self.assertTrue(d.called)

    def test_task_sleep(self):
        called = []
        def func():
            called.append(None)
            flubber.sleep(0.001)
            called.append(None)
        flubber.spawn(func)
        t0 = time.time()
        self.loop.run()
        t1 = time.time()
        self.assertEqual(len(called), 2)
        self.assertTrue(0 <= t1-t0 < 0.1)

    def test_spawn_order(self):
        called = []
        def func(x):
            called.append(x)
        for i in range(5):
            flubber.spawn(func, i)
        self.loop.run()
        self.assertEqual(called, range(5))

    def test_custom_task(self):
        task = MyTask()
        task.start()
        self.loop.run()
        self.assertTrue(task.called)

    def test_kill_running(self):
        called = []
        def func():
            flubber.sleep(0)
            called.append(None)
            flubber.sleep(0)
            called.append(None)
        task1 = flubber.spawn(func)
        task2 = flubber.spawn(task1.kill)
        self.loop.run()
        self.assertEqual(len(called), 1)

    def test_run_order(self):
        called = []
        def func(x):
            called.append(x)
            flubber.sleep(0)
            called.append(x)
        flubber.spawn(func, 1)
        flubber.spawn(func, 2)
        flubber.spawn(func, 3)
        self.loop.run()
        self.assertEqual(called, [1, 2, 3, 1, 2, 3])

    def test_task_join(self):
        d = dummy()
        d.called = False
        def func1():
            flubber.sleep(0.01)
        def func2():
            d.called = t1.join()
        t1 = flubber.spawn(func1)
        t2 = flubber.spawn(func2)
        self.loop.run()
        self.assertTrue(d.called)

    def test_task_join_timeout(self):
        d = dummy()
        d.called = False
        def func1():
            flubber.sleep(10)
        def func2():
            d.called = t1.join(0.01)
        def func3():
            flubber.sleep(0.1)
            t1.kill()
        t1 = flubber.spawn(func1)
        t2 = flubber.spawn(func2)
        t3 = flubber.spawn(func3)
        self.loop.run()
        self.assertTrue(not d.called)

    def test_task_bogus_switch(self):
        def func1():
            flubber.sleep(0)
            flubber.sleep(0)
        def func2():
            self.assertRaises(RuntimeError, t1.switch)
            self.assertRaises(RuntimeError, t1.throw)
        t1 = flubber.spawn(func1)
        t2 = flubber.spawn(func2)
        self.loop.run()

#    def test_task_exception(self):
#        def func():
#            1/0
#        flubber.spawn(func)
#        self.loop.run()


if __name__ == '__main__':
    unittest.main(verbosity=2)

