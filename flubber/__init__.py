
version_info = (0, 9, 17, "dev")
__version__ = ".".join(map(str, version_info))

from flubber import greenthread
from flubber import timeout
from flubber import net

sleep = greenthread.sleep
spawn = greenthread.spawn
spawn_after = greenthread.spawn_after
kill = greenthread.kill

Timeout = timeout.Timeout

connect = net.connect
listen = net.listen

import flubber.core
core = flubber.core.setup()

