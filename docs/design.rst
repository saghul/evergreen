
Design
======

The following sections contain an explanation of the design of the
different parts that compose evergreen. Evergreen was inspired by similar
libraries such as Gevent and Eventlet, but some of the key ideas
are different:

- Limit the amount of 'magic' to the minimum possible
- Cooperative tasks should look like threads
- APIs for dealing with tasks should mimic those used
  in threading
- Task scheduling has to be predictable and consistent,
  but without being exposed to the user
- The event loop (or hub or reactor) is a first class citizen
  and it's not hidden


Event loop
----------

The event loop can be considered the central point of evergreen, it deals with timers,
I/O and task scheduling (described later). The event loop API is heavily inspired
by PEP 3156, so it's possible that in the future the event loop implementation evergreen
uses can be replaced. At the moment evergreen uses `puyv <https://github.com/saghul/pyuv>`_
as the underlying event loop.

In evergreen only one loop may exist per thread, and it has to be manually created for threads
other than the main thread. This would be the structure of a normal program using evergreen:

::

    import evergreen

    # Create the global loop
    loop = evergreen.EventLoop()

    # Setup tasks
    ...

    # Start the loop
    loop.run()


No tasks will start working until `loop.run` is called unless a blocking operation is performed,
in which case the loop is automatically started. For long running processes such as servers, it's
advised to explicitly create the event loop, setup tasks and manually run it. Small scripts can
rely on the fact that the main thread's loop is automatically created and run when an opperation
cooperatively blocks.


Tasks
-----

The cooperative task abstraction provided by evergreen (through the :class:`Task` class).
The public API for this class mimics that of a `threading.Thread` thread, but it's
scheduled cooperatively.

Tasks are implemented using the `fibers <https://github.com/saghul/python-fibers>`_ library.

Here are some 'rules' that apply to tasks:

- Tasks don't yield control to each other, they must always yield control to the loop,
  or schedule a switch to the desired task in the loop, this ensures predictable
  execution order and fairness.
- In order to exchange values between tasks any of the provided synchronization
  primitives should be used, the tasks themselves don't provide any means to do it.


Scheduling
----------

The scheduler has no public interface. You interact with it by switching execution to the loop.
In fact, there is no single object representing the scheduler, its behavior is implemented by the
Task, Future and other classes using only the public interface of the event loop.

The easiest way to suspend the execution of the current task and yield control to the loop so that
other tasks can run is to use:

::

    evergreen.sleep(0)

The only functions that suspend the current task are those which 'block', for example lock or
socket functions.

