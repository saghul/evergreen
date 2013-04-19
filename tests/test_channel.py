
from common import unittest, EvergreenTestCase

import evergreen


class ChannelTests(EvergreenTestCase):

    def test_channel_simple(self):
        ch = evergreen.Channel()
        def sender():
            ch.send('test')
        def receiver():
            self.assertEqual(ch.receive(), 'test')
        evergreen.spawn(sender)
        evergreen.spawn(receiver)
        self.loop.run()

    def test_channel_exception(self):
        ch = evergreen.Channel()
        def sender():
            ch.send_exception(RuntimeError)
        def receiver():
            self.assertRaises(RuntimeError, ch.receive)
        evergreen.spawn(sender)
        evergreen.spawn(receiver)
        self.loop.run()

    def test_channel_iter(self):
        ch = evergreen.Channel()
        def sender():
            ch.send('hello')
            evergreen.sleep(0)
            ch.send('world')
            evergreen.sleep(0)
            ch.send_exception(StopIteration)
        def receiver():
            items = []
            for item in ch:
                items.append(item)
            self.assertEqual(items, ['hello', 'world'])
        evergreen.spawn(sender)
        evergreen.spawn(receiver)
        self.loop.run()

    def test_channel_multiple_waiters(self):
        ch = evergreen.Channel()
        def sender():
            ch.send('hello')
            ch.send('world')
        def receiver1():
            self.assertEqual(ch.receive(), 'hello')
        def receiver2():
            self.assertEqual(ch.receive(), 'world')
        evergreen.spawn(sender)
        evergreen.spawn(receiver1)
        evergreen.spawn(receiver2)
        self.loop.run()

    def test_channel_iter(self):
        ch = evergreen.Channel()
        def sender1():
            ch.send('hello')
        def sender2():
            ch.send('world')
            ch.send_exception(StopIteration)
        def receiver():
            items = []
            for item in ch:
                items.append(item)
            self.assertEqual(items, ['hello', 'world'])
        evergreen.spawn(sender1)
        evergreen.spawn(sender2)
        evergreen.spawn(receiver)
        self.loop.run()


if __name__ == '__main__':
    unittest.main(verbosity=2)

