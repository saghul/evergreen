
from common import dummy, unittest, EvergreenTestCase

import evergreen
import time


class MyTask(evergreen.Task):
    called = False

    def run_(self):
        self.called = True


class TasksTests(EvergreenTestCase):

    def test_simple_task(self):
        d = dummy()
        d.called = False
        def func():
            d.called = True
        task = evergreen.Task(target=func)
        task.start()
        self.loop.run()
        self.assertTrue(d.called)

    def test_spawn(self):
        d = dummy()
        d.called = False
        def func():
            d.called = True
        evergreen.spawn(func)
        self.loop.run()
        self.assertTrue(d.called)

    def test_spawn_kill(self):
        d = dummy()
        d.called = False
        def func():
            d.called = True
        task = evergreen.spawn(func)
        task.kill()
        self.loop.run()
        self.assertFalse(d.called)

    def test_spawn_kill_join(self):
        d = dummy()
        d.called = False
        def func1():
            d.called = True
        def func2():
            self.assertTrue(t1.join())
        t1 = evergreen.spawn(func1)
        t1.kill()
        t2 = evergreen.spawn(func2)
        self.loop.run()
        self.assertFalse(d.called)

    def test_task_decorator(self):
        d = dummy()
        d.called = False
        @evergreen.task
        def func():
            d.called = True
        func()
        self.loop.run()
        self.assertTrue(d.called)

    def test_task_sleep(self):
        called = []
        def func():
            called.append(None)
            evergreen.sleep(0.001)
            called.append(None)
        evergreen.spawn(func)
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
            evergreen.spawn(func, i)
        self.loop.run()
        self.assertEqual(called, [0, 1, 2, 3, 4])

    def test_custom_task(self):
        task = MyTask()
        task.start()
        self.loop.run()
        self.assertTrue(task.called)

    def test_kill_running(self):
        called = []
        def func():
            evergreen.sleep(0)
            called.append(None)
            evergreen.sleep(0)
            called.append(None)
        task1 = evergreen.spawn(func)
        task2 = evergreen.spawn(task1.kill)
        self.loop.run()
        self.assertEqual(len(called), 1)

    def test_run_order(self):
        called = []
        def func(x):
            called.append(x)
            evergreen.sleep(0)
            called.append(x)
        evergreen.spawn(func, 1)
        evergreen.spawn(func, 2)
        evergreen.spawn(func, 3)
        self.loop.run()
        self.assertEqual(called, [1, 2, 3, 1, 2, 3])

    def test_task_join(self):
        d = dummy()
        d.called = False
        def func1():
            evergreen.sleep(0.01)
        def func2():
            d.called = t1.join()
        t1 = evergreen.spawn(func1)
        t2 = evergreen.spawn(func2)
        self.loop.run()
        self.assertTrue(d.called)

    def test_task_join_timeout(self):
        d = dummy()
        d.called = False
        def func1():
            evergreen.sleep(10)
        def func2():
            d.called = t1.join(0.01)
        def func3():
            evergreen.sleep(0.1)
            t1.kill()
        t1 = evergreen.spawn(func1)
        t2 = evergreen.spawn(func2)
        t3 = evergreen.spawn(func3)
        self.loop.run()
        self.assertTrue(not d.called)

    def test_task_bogus_switch(self):
        def func1():
            evergreen.sleep(0)
            evergreen.sleep(0)
        def func2():
            self.assertRaises(RuntimeError, t1.switch)
            self.assertRaises(RuntimeError, t1.throw)
        t1 = evergreen.spawn(func1)
        t2 = evergreen.spawn(func2)
        self.loop.run()

#    def test_task_exception(self):
#        def func():
#            1/0
#        evergreen.spawn(func)
#        self.loop.run()


if __name__ == '__main__':
    unittest.main(verbosity=2)

