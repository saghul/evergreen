
.. module:: evergreen.futures

Futures
=======

This module implements an (almost) API compatible `concurrent.futures` implementation
which is copperative.


.. py:class:: Future

    The Future class encapsulates the asynchronous execution of a callable. Future
    instances are created by Executor.submit().

    .. py:method:: cancel

        Attempt to cancel the call. If the call is currently being executed and cannot
        be cancelled then the method will return False, otherwise the call will be cancelled
        and the method will return True.

    .. py:attribute:: cancelled

        Return True if the call was successfully cancelled.

    .. py:attribute:: done

        Return True if the call was successfully cancelled or finished running.

    .. py:attribute:: running

        Return True if the call is currently being executed and cannot be cancelled.

    .. py:method:: get(timeout=None)

        Return the value returned by the call. If the call hasn’t yet completed then
        this method will wait up to timeout seconds. If the call hasn’t completed in
        timeout seconds, then a TimeoutError will be raised. timeout can be an int or
        float. If timeout is not specified or None, there is no limit to the wait time.

        If the future is cancelled before completing then CancelledError will be raised.

        If the call raised, this method will raise the same exception.

    .. py:method:: add_done_callback(func)

        Attaches the callable func to the future. func will be called, with the future as
        its only argument, when the future is cancelled or finishes running.

        Added callables are called in the order that they were added and are always called
        in a thread belonging to the process that added them. If the callable raises a
        Exception subclass, it will be logged and ignored. If the callable raises a BaseException
        subclass, the behavior is undefined.

        If the future has already completed or been cancelled, func will be called immediately.


.. py:class:: Executor

    An abstract class that provides methods to execute calls asynchronously.  It
    should not be used directly, but through its concrete subclasses.

    .. py:method:: submit(fn, \*args, \*\*kwargs)

        Schedules the callable, *fn*, to be executed as ``fn(*args **kwargs)``
        and returns a :class:`Future` object representing the execution of the
        callable. ::

           with ThreadPoolExecutor(max_workers=1) as executor:
               future = executor.submit(pow, 323, 1235)
               print(future.result())

    .. py:method:: map(func, \*iterables, timeout=None)

        Equivalent to ``map(func, *iterables)`` except *func* is executed
        asynchronously and several calls to *func* may be made concurrently.  The
        returned iterator raises a :exc:`TimeoutError` if
        :meth:`~iterator.__next__` is called and the result isn't available
        after *timeout* seconds from the original call to :meth:`Executor.map`.
        *timeout* can be an int or a float.  If *timeout* is not specified or
        ``None``, there is no limit to the wait time.  If a call raises an
        exception, then that exception will be raised when its value is
        retrieved from the iterator.

    .. py:method:: shutdown(wait=True)

        Signal the executor that it should free any resources that it is using
        when the currently pending futures are done executing.  Calls to
        :meth:`Executor.submit` and :meth:`Executor.map` made after shutdown will
        raise :exc:`RuntimeError`.

        If *wait* is ``True`` then this method will not return until all the
        pending futures are done executing and the resources associated with the
        executor have been freed.  If *wait* is ``False`` then this method will
        return immediately and the resources associated with the executor will be
        freed when all pending futures are done executing.  Regardless of the
        value of *wait*, the entire Python program will not exit until all
        pending futures are done executing.

        You can avoid having to call this method explicitly if you use the
        `with` statement, which will shutdown the :class:`Executor`
        (waiting as if :meth:`Executor.shutdown` were called with *wait* set to ``True``)

        ::

           import shutil
           with ThreadPoolExecutor(max_workers=4) as e:
               e.submit(shutil.copy, 'src1.txt', 'dest1.txt')
               e.submit(shutil.copy, 'src2.txt', 'dest2.txt')
               e.submit(shutil.copy, 'src3.txt', 'dest3.txt')
               e.submit(shutil.copy, 'src3.txt', 'dest4.txt')


.. py:class:: TaskPoolExecutor(max_workers)

    An :class:`Executor` subclass that uses a pool of at most `max_workers` tasks to execute
    calls concurrently.


.. py:class:: ThreadPoolExecutor(max_workers)

    An :class:`Executor` subclass that uses a pool of at most `max_workers` threads to execute
    calls asynchronously.


.. py:function:: wait(fs, timeout=None, return_when=ALL_COMPLETED)

    Wait for the :class:`Future` instances (possibly created by different
    :class:`Executor` instances) given by *fs* to complete.  Returns a named
    2-tuple of sets.  The first set, named ``done``, contains the futures that
    completed (finished or were cancelled) before the wait completed.  The second
    set, named ``not_done``, contains uncompleted futures.

    *timeout* can be used to control the maximum number of seconds to wait before
    returning.  *timeout* can be an int or float.  If *timeout* is not specified
    or ``None``, there is no limit to the wait time.

    *return_when* indicates when this function should return.  It must be one of
    the following constants:

    +-----------------------------+----------------------------------------+
    | Constant                    | Description                            |
    +=============================+========================================+
    | :const:`FIRST_COMPLETED`    | The function will return when any      |
    |                             | future finishes or is cancelled.       |
    +-----------------------------+----------------------------------------+
    | :const:`FIRST_EXCEPTION`    | The function will return when any      |
    |                             | future finishes by raising an          |
    |                             | exception.  If no future raises an     |
    |                             | exception then it is equivalent to     |
    |                             | :const:`ALL_COMPLETED`.                |
    +-----------------------------+----------------------------------------+
    | :const:`ALL_COMPLETED`      | The function will return when all      |
    |                             | futures finish or are cancelled.       |
    +-----------------------------+----------------------------------------+


.. py:function:: as_completed

    Returns an iterator over the :class:`Future` instances (possibly created by
    different :class:`Executor` instances) given by *fs* that yields futures as
    they complete (finished or were cancelled).  Any futures that completed
    before :func:`as_completed` is called will be yielded first.  The returned
    iterator raises a :exc:`TimeoutError` if :meth:`~iterator.__next__` is
    called and the result isn't available after *timeout* seconds from the
    original call to :func:`as_completed`.  *timeout* can be an int or float.
    If *timeout* is not specified or ``None``, there is no limit to the wait
    time.


Exceptions
----------

.. py:exception:: CancelledError


.. py:exception:: TimeoutError


Future class API changes
------------------------

The future class in this module doesn't conform 100% to the API exposed
by the equivalent class in the `concurrent.futures` module from the
standard library, though they are pretty minor. Here is the list of changes:

- `cancelled`, `done` and `running` are properties, not functions
- `result` function is called `get`
- there is no `exception` function

