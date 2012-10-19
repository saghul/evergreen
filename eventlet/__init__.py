
version_info = (0, 9, 17, "dev")
__version__ = ".".join(map(str, version_info))

from eventlet import greenthread
from eventlet import timeout
from eventlet import convenience

sleep = greenthread.sleep
suspend = greenthread.suspend
spawn = greenthread.spawn
spawn_after = greenthread.spawn_after
kill = greenthread.kill

Timeout = timeout.Timeout

connect = convenience.connect
listen = convenience.listen

import eventlet.core
core = eventlet.core.setup()

