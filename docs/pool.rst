
.. module:: flubber.pool

Task pools
==========

Pool objects provide a way to limit the amount of running tasks. If a Pool is defined
to use X tasks and spawning a new one is attempted, the caller will block until another
task is finished.


.. py:class:: Pool([size])

    Initialize a task pool of the given size. It defaults to 1000.

    .. py:method:: spawn(func, \*args, \*\*kwargs)

        Spawn a new task off the pool.

    .. py:method:: join([timeout])

        Wait until all tasks are finished or the specified timeout is elapsed.

