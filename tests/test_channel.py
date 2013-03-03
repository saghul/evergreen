
from common import unittest, FlubberTestCase

import flubber


class ChannelTests(FlubberTestCase):

    def test_channel_simple(self):
        ch = flubber.Channel()
        def sender():
            ch.send('test')
        def receiver():
            self.assertEqual(ch.receive(), 'test')
        flubber.spawn(sender)
        flubber.spawn(receiver)
        self.loop.run()

    def test_channel_exception(self):
        ch = flubber.Channel()
        def sender():
            ch.send_exception(RuntimeError)
        def receiver():
            self.assertRaises(RuntimeError, ch.receive)
        flubber.spawn(sender)
        flubber.spawn(receiver)
        self.loop.run()

    def test_channel_iter(self):
        ch = flubber.Channel()
        def sender():
            ch.send('hello')
            flubber.sleep(0)
            ch.send('world')
            flubber.sleep(0)
            ch.send_exception(StopIteration)
        def receiver():
            items = []
            for item in ch:
                items.append(item)
            self.assertEqual(items, ['hello', 'world'])
        flubber.spawn(sender)
        flubber.spawn(receiver)
        self.loop.run()

    def test_channel_multiple_waiters(self):
        ch = flubber.Channel()
        def sender():
            ch.send('hello')
            ch.send('world')
        def receiver1():
            self.assertEqual(ch.receive(), 'hello')
        def receiver2():
            self.assertEqual(ch.receive(), 'world')
        flubber.spawn(sender)
        flubber.spawn(receiver1)
        flubber.spawn(receiver2)
        self.loop.run()

    def test_channel_iter(self):
        ch = flubber.Channel()
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
        flubber.spawn(sender1)
        flubber.spawn(sender2)
        flubber.spawn(receiver)
        self.loop.run()


if __name__ == '__main__':
    unittest.main(verbosity=2)

