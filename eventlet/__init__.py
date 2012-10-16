
version_info = (0, 9, 17, "dev")
__version__ = ".".join(map(str, version_info))

from eventlet import greenthread
from eventlet import greenpool
from eventlet import queue
from eventlet import timeout
from eventlet import patcher
from eventlet import convenience

sleep = greenthread.sleep
spawn = greenthread.spawn
spawn_after = greenthread.spawn_after
kill = greenthread.kill

Timeout = timeout.Timeout
with_timeout = timeout.with_timeout

GreenPool = greenpool.GreenPool
GreenPile = greenpool.GreenPile

Queue = queue.Queue

import_patched = patcher.import_patched
monkey_patch = patcher.monkey_patch

connect = convenience.connect
listen = convenience.listen

