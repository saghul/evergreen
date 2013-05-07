
from common import dummy, unittest, EvergreenTestCase

import re
import sys

import evergreen
from evergreen.io import tcp, pipe
from evergreen.io.util import ReadBuffer


if sys.platform == 'win32':
    TEST_PIPE = '\\\\.\\pipe\\test-pipe'
else:
    TEST_PIPE = 'test-pipe'
TEST_PORT = 1234
TEST_SERVER = ('0.0.0.0', TEST_PORT)
TEST_CLIENT = ('127.0.0.1', TEST_PORT)


class EchoTCPServer(tcp.TCPServer):

    @evergreen.task
    def handle_connection(self, connection):
        while True:
            data = connection.read_until('\n')
            if not data:
                break
            connection.write(data)


class EchoPipeServer(pipe.PipeServer):

    @evergreen.task
    def handle_connection(self, connection):
        while True:
            data = connection.read_until('\n')
            if not data:
                break
            connection.write(data)


class BufferTest(unittest.TestCase):

    def test_read(self):
        buf = ReadBuffer()
        buf.feed(b'hello world')
        data = buf.read(5)
        self.assertEqual(data, b'hello')
        data = buf.read(6)
        self.assertEqual(data, b' world')
        data = buf.read(100)
        self.assertEqual(data, None)

    def test_read_until(self):
        buf = ReadBuffer()
        buf.feed(b'hello\nworld\n')
        data = buf.read_until(b'\n')
        self.assertEqual(data, b'hello\n')
        data = buf.read_until(b'\n')
        self.assertEqual(data, b'world\n')
        data = buf.read_until(b'\n')
        self.assertEqual(data, None)

    def test_read_until_regex(self):
        regex = re.compile(b'~~')
        buf = ReadBuffer()
        buf.feed(b'hello~~world~~')
        data = buf.read_until_regex(regex)
        self.assertEqual(data, b'hello~~')
        data = buf.read_until_regex(regex)
        self.assertEqual(data, b'world~~')
        data = buf.read_until_regex(regex)
        self.assertEqual(data, None)

    def test_clear(self):
        buf = ReadBuffer()
        buf.feed(b'hello world')
        buf.clear()
        data = buf.read(5)
        self.assertEqual(data, None)

    def test_close(self):
        buf = ReadBuffer()
        buf.feed(b'hello world')
        buf.close()
        self.assertTrue(buf.closed)
        self.assertRaises(ValueError, buf.read, 5)


class IOTests(EvergreenTestCase):

    def _start_tcp_echo_server(self):
        self.server = EchoTCPServer()
        self.server.bind(TEST_SERVER)
        self.server.serve()

    def test_tcp_read(self):
        def connect():
            client = tcp.TCPClient()
            client.connect(TEST_CLIENT)
            client.write(b'PING\n')
            data = client.read_until(b'\n')
            self.assertEqual(data, b'PING\n')
            client.close()
            self.server.close()
        evergreen.spawn(self._start_tcp_echo_server)
        evergreen.spawn(connect)
        self.loop.run()

    def test_tcp_read_error(self):
        def connect():
            client = tcp.TCPClient()
            client.connect(TEST_CLIENT)
            client.close()
            self.assertRaises(tcp.TCPError, client.read_until, b'\n')
            self.server.close()
        evergreen.spawn(self._start_tcp_echo_server)
        evergreen.spawn(connect)
        self.loop.run()

    def _start_pipe_echo_server(self):
        self.server = EchoPipeServer()
        self.server.bind(TEST_PIPE)
        self.server.serve()

    def test_pipe_read(self):
        def connect():
            client = pipe.PipeClient()
            client.connect(TEST_PIPE)
            client.write(b'PING\n')
            data = client.read_until(b'\n')
            self.assertEqual(data, b'PING\n')
            client.close()
            self.server.close()
        evergreen.spawn(self._start_pipe_echo_server)
        evergreen.spawn(connect)
        self.loop.run()

    def test_pipe_read_error(self):
        def connect():
            client = pipe.PipeClient()
            client.connect(TEST_PIPE)
            client.close()
            self.assertRaises(pipe.PipeError, client.read_until, b'\n')
            self.server.close()
        evergreen.spawn(self._start_pipe_echo_server)
        evergreen.spawn(connect)
        self.loop.run()


if __name__ == '__main__':
    unittest.main(verbosity=2)

