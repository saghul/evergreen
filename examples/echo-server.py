
import sys

import evergreen
from evergreen import net

loop = evergreen.EventLoop()


def handle(fd):
    print("client connected")
    while True:
        x = fd.readline()
        if not x:
            break
        fd.write(x)
        fd.flush()
        print("echoed {}".format(x))
    print("client disconnected")


def echo_server():
    port = int(sys.argv[1] if len(sys.argv) > 1 else 6000)
    print("server socket listening on port {}".format(port))
    server = net.listen('tcp:0.0.0.0:{}'.format(port))
    while True:
        new_sock, address = server.accept()
        print("accepted connection from {}".format(address))
        evergreen.spawn(handle, new_sock.makefile('rw'))


evergreen.spawn(echo_server)
loop.run()

