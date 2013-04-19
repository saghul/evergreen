
import sys

import evergreen
from evergreen.io import tcp

loop = evergreen.EventLoop()


class EchoServer(tcp.TCPServer):

    @evergreen.task
    def handle_connection(self, connection):
        print('client connected from {}'.format(connection.peername))
        while True:
            data = connection.read_until('\n')
            if not data:
                break
            connection.write(data)
        print('connection closed')


def main():
    server = EchoServer()
    port = int(sys.argv[1] if len(sys.argv) > 1 else 1234)
    server.bind(('0.0.0.0', port))
    print ('listening on {}'.format(server.sockname))
    server.serve()


evergreen.spawn(main)
loop.run()

