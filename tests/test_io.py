
from common import dummy, unittest, EvergreenTestCase

import re
import sys

import evergreen
from evergreen.io import tcp, pipe, udp
from evergreen.io.util import StringBuffer


if sys.platform == 'win32':
    TEST_PIPE = '\\\\.\\pipe\\test-pipe'
else:
    TEST_PIPE = 'test-pipe'
TEST_PORT = 1234
TEST_SERVER = ('0.0.0.0', TEST_PORT)
TEST_CLIENT = ('127.0.0.1', TEST_PORT)
TEST_UDP_ENDPOINT = TEST_CLIENT


class EchoMixin(object):

    @evergreen.task
    def handle_connection(self, connection):
        while True:
            data = connection.read_until(b'\n')
            if not data:
                break
            connection.write(data)
            connection.flush()
            if connection.closed:
                # Connection might have been closed after we flushed
                break


class EchoTCPServer(EchoMixin, tcp.TCPServer):
    pass


class EchoPipeServer(EchoMixin, pipe.PipeServer):
    pass


class BufferTest(unittest.TestCase):

    def test_read(self):
        buf = StringBuffer()
        buf.feed(b'hello world')
        data = buf.read(5)
        self.assertEqual(data, b'hello')
        data = buf.read(6)
        self.assertEqual(data, b' world')
        data = buf.read(100)
        self.assertEqual(data, None)

    def test_read_until(self):
        buf = StringBuffer()
        buf.feed(b'hello\nworld\n')
        data = buf.read_until(b'\n')
        self.assertEqual(data, b'hello\n')
        data = buf.read_until(b'\n')
        self.assertEqual(data, b'world\n')
        data = buf.read_until(b'\n')
        self.assertEqual(data, None)

    def test_read_until_regex(self):
        regex = re.compile(b'~~')
        buf = StringBuffer()
        buf.feed(b'hello~~world~~')
        data = buf.read_until_regex(regex)
        self.assertEqual(data, b'hello~~')
        data = buf.read_until_regex(regex)
        self.assertEqual(data, b'world~~')
        data = buf.read_until_regex(regex)
        self.assertEqual(data, None)

    def test_clear(self):
        buf = StringBuffer()
        buf.feed(b'hello world')
        buf.clear()
        data = buf.read(5)
        self.assertEqual(data, None)

    def test_close(self):
        buf = StringBuffer()
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
            client.sockname    # for coverage
            client.peername    # for coverage
            r = client.write(b'PING\n')
            self.assertTrue(r)
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
            evergreen.sleep(0.1)  # give it some time to stabilize
            client.close()
            self.assertRaises(tcp.TCPError, client.read_until, b'\n')
            self.server.close()
        evergreen.spawn(self._start_tcp_echo_server)
        evergreen.spawn(connect)
        self.loop.run()

    def test_tcp_shutdown(self):
        def connect():
            client = tcp.TCPClient()
            client.connect(TEST_CLIENT)
            while True:
                if not client.write(b'PING\n'):
                    break
            client.shutdown()
            client.close()
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
            evergreen.sleep(0.1)  # give it some time to stabilize
            client.close()
            self.assertRaises(pipe.PipeError, client.read_until, b'\n')
            self.server.close()
        evergreen.spawn(self._start_pipe_echo_server)
        evergreen.spawn(connect)
        self.loop.run()

    def _start_udp_echo_server(self):
        self.server = udp.UDPEndpoint()
        self.server.bind(TEST_UDP_ENDPOINT)
        self.server.sockname    # for coverage
        try:
            while True:
                data, addr = self.server.receive()
                self.server.send(data, addr)
                self.server.flush()
        except udp.UDPError:
            pass

    def test_udp_ping_pong(self):
        def connect():
            client = udp.UDPEndpoint()
            client.send(b'PING', TEST_UDP_ENDPOINT)
            client.flush()
            data, addr = client.receive()
            self.assertEqual(data, b'PING')
            client.close()
            self.assertRaises(udp.UDPError, client.receive)
            self.server.close()
        evergreen.spawn(self._start_udp_echo_server)
        evergreen.spawn(connect)
        self.loop.run()


if __name__ == '__main__':
    unittest.main(verbosity=2)

