
.. module:: evergreen.tasks

Task: a cooperative *thread*
============================

The tasks module provides one of the most important pieces of evergreen, the `Task`
class along with some utility functions. The `Task` class encapsulates a unit
of cooperative work and it has an API which is very similar to the `Thread` class
in the standard library.


.. py:function:: sleep(seconds)

    Suspend the current task until the given amount of time has elapsed.


.. py:function:: spawn(func, \*args, \*\*kwargs)

    Create a `Task` object to run `func(*args, **kwargs)` and start it.
    Returns the `Task` object.


.. py:function:: task

    Decorator to run the decorated function in a `Task`.


.. py:class:: Task(target=None, args=(), kwargs={})

    Runs the given target function with the specified arguments as a cooperative
    task.

    .. py:classmethod:: current

        Returns the current running task instance.

    .. py:method:: start

        Schedules the task to be run.

    .. py:method:: run

        Main method the task will execute. Subclasses may want to override this method
        instead of passing arguments to __init__.

    .. py:method:: join(timeout=None)

        Wait until the task finishes for the given amount of time. Returns a boolean flag
        indicating if the task finished the work or not.

    .. py:method:: kill(typ=TaskExit, [value, [tb]])

        Raises the given exception (`TaskExit` by default) in the task. If the task wasn't
        run yet it will be raised the moment it runs. If the task was already running, it will
        be raised when it yields control.

        Calling this function doesn't unschedule the current task.

.. py:exception:: TaskExit

    Exception used to kill a single task. It does not propagate.


