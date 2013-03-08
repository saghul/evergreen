
.. module:: flubber.loop

The Event Loop
==============

The event loop is the main entity in flubber, together with tasks. It takes care of running
all scheduled operations and provides time based callback scheduling as well as i/o readyness
based callback scheduling.


.. py:class:: EventLoop

    This is the main class that sets things in motion in flubber. I runs scheduled tasks,
    timers and i/o operations. Only one event loop may exist per thread and it needs to be
    explicitly created. The current loop can be accessed with `flubber.current.loop`.

    .. py:attribute:: DEFAULT_EXECUTOR_WORKERS

        Number of workers for the default executor.

    .. py:method:: call_soon(callback, \*args, \*\*kw)

        Schedule the given callback to be called as soon as possible. Returns a `Handler`
        object which can be used to cancel the callback.

    .. py:method:: call_from_thread(callback, \*args, \*\*kw)

        Schedule the given callback to be called by the loop thread. This is the
        only thread-safe function on the loop. Returns a `Handler`
        object which can be used to cancel the callback.

    .. py:method:: call_later(delay, callback, \*args, \*\*kw)

        Schedule the given callback to be called after the given amount
        of time. Returns a `Handler` object which can be used to cancel the callback.

    .. py:method:: call_repeatedly(interval, callback, \*args, \*\*kw)

        Schedule the given callback to be called at the given time
        intervals. Returns a `Handler` object which can be used to cancel the
        callback.

    .. py:method:: run_in_executor(executor, callback, \*args, \*\*kw)

        Run the given callback in the given executor. In case it's None,
        a default `TaskPoolExecutor` will be created with `DEFAULT_EXECUTOR_WORKERS`
        size. Returns a `Future` instance.

    .. py:method:: set_default_executor(executor)

        Set the default executor.

    .. py:method:: add_reader(fd, callback, \*args, \*\*kw)

        Create a handler which will call the given callback when the given
        file descriptor is ready for reading. Returns a `Handler` instance which
        can be used to cancel the operation.

    .. py:method:: remove_reader(fd)

        Remove the read handler for the given file descriptor.

    .. py:method:: add_writer(fd, callback, \*args, \*\*kw)

        Create a handler which will call the given callback when the given
        file descriptor is ready for writing.

    .. py:method:: remove_writer(fd)

        Remove the write handler for the given file descriptor. Returns a `Handler`
        instance which can be used to cancel the operation.

    .. py:method:: switch

        Switch task execution to the loop's main task.

    .. py:method:: run

        Start running the event loop. It will be automatically stopped when
        there are no more scheduled tasks or callbacks to run.

        .. note::
            Once the loop has been stopped it cannot be started again.

    .. py:method:: stop

        Stop the event loop. It's not necessary to call stop in order
        for `run` to return because it will return once there is no more
        work to do. However, in certain cases like fatal failures it may
        be appropriate to prematurely stop running the loop, this function
        can be used in those cases.


.. py:class:: Handler

    This is an internal class which is returned by many of the `EventLoop`
    methods and provides a way to cancel scheduled callbacks.

    .. note::
        This class should not be instantiated by user applications, the loop
        itself uses it to wrap callbacks and return it to the user.

    .. py:method:: cancel

        Cancels the handle, preventing its callback from being executed,
        if it wasn't executed yet.


Finding the 'current loop'
--------------------------

Flubber provides a convenience mechanism to get a reference to the loop
running in the current thread:

::

    current_loop = flubber.current.loop

If a loop was not explicitly created in the current thread :exc:`RuntimeError`
is raised.

