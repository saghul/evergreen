
.. module:: evergreen.loop

The Event Loop
==============

The event loop is the main entity in evergreen, together with tasks. It takes care of running
all scheduled operations and provides time based callback scheduling as well as I/O readyness
based callback scheduling.


.. py:class:: EventLoop

    This is the main class that sets things in motion in evergreen. I runs scheduled tasks,
    timers and I/O operations. Only one event loop may exist per thread and it needs to be
    explicitly created for threads other than the main thread.
    The current loop can be accessed with `evergreen.current.loop`.

    .. py:classmethod:: current

        Returns the event loop instance running in the current thread.

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

    .. py:method:: call_at(when, callback, \*args, \*\*kw)

        Schedule the given callback to be called at the given time. Returns a `Handler` object
        which can be used to cancel the callback.

    .. py:method:: time()

        Returns the current time.

    .. py:method:: add_reader(fd, callback, \*args, \*\*kw)

        Create a handler which will call the given callback when the given
        file descriptor is ready for reading.

    .. py:method:: remove_reader(fd)

        Remove the read handler for the given file descriptor.

    .. py:method:: add_writer(fd, callback, \*args, \*\*kw)

        Create a handler which will call the given callback when the given
        file descriptor is ready for writing.

    .. py:method:: remove_writer(fd)

        Remove the write handler for the given file descriptor.

    .. py:method:: add_signal_handler(signum, callback, \*args, \*\*kw)

        Create a handler which will run the given callback when the specified
        signal is captured. Multiple handlers for the same signal can be added.
        If the handler is cancelled, only *that* particular handler is removed.

    .. py:method:: remove_signal_handler(signum)

        Remove all handlers for the specified signal.

    .. py:method:: switch

        Switch task execution to the loop's main task. If the loop wasn't started yet
        it will be started at this point.

    .. py:method:: run

        Start running the event loop. It will be automatically stopped when
        there are no more scheduled tasks or callbacks to run.

        .. note::
            Once the loop has been stopped it cannot be started again.

    .. py:method:: run_forever

        Similar to `run` but it will not stop be stopped automatically even if
        all tasks are finished. The loop will be stopped when `stop()` is called.
        Useful for long running processes such as servers.

    .. py:method:: stop

        Stop the event loop.

    .. py:method:: destroy

        Free all resources associated with an event loop. The thread local
        storage is also emptied, so after destroying a loop a new one can be created
        on the same thread.


.. py:class:: Handler

    This is an internal class which is returned by many of the `EventLoop`
    methods and provides a way to cancel scheduled callbacks.

    .. note::
        This class should not be instantiated by user applications, the loop
        itself uses it to wrap callbacks and return it to the user.

    .. py:method:: cancel

        Cancels the handle, preventing its callback from being executed,
        if it wasn't executed yet.

        .. warning::
            Like every API method other than `EventLoop.call_from_thread`, this
            function is not thread safe, it must be called from the event loop
            thread.


Finding the 'current loop'
--------------------------

evergreen provides a convenience mechanism to get a reference to the loop
running in the current thread:

::

    current_loop = evergreen.current.loop

If a loop was not explicitly created in the current thread :exc:`RuntimeError`
is raised.


Handling signals
----------------

While the `signal` module works just fine, it's better to use the signal handling
functions provided by the `EventLoop`. It allows adding multiple handlers for the
same signal, from different threads and the handlers are called in the appropriate
thread (where they were added from).

