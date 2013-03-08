
Design
======

The following sections contain en explanation the design of the
different parts that compose flubber. Flubber was inspired by similar
libraries such as Gevent and Eventlet, but some of the key ideas
are different:

- Limit the amount of 'magic' to the minimum possible
- Cooperative tasks should look like threads
- APIs for dealing with tasks should mimic those used
  in threading
- Task scheduling has to be predictable and consistent,
  but without being exposed to the user
- The event loop (or hub or reactor) must be explicitly
  created


Event loop
----------

The event loop can be considered the central point of flubber, it deals with timers,
i/o and task scheduling (described later). The event loop API is heavily inspired
by PEP 3156, so it's possible that in the future the event loop implementation flubber
uses can be replaced. At the moment flubber uses `puyv <https://github.com/saghul/pyuv>`_
as the underlying event loop.

In flubber only one loop may exist per thread, but it has to be manually created and
run. This would be the structure of a normal program using flubber:

::

    import flubber

    # Create the global loop
    loop = flubber.EventLoop()

    # Setup tasks
    ...

    # Start the loop
    loop.run()


No tasks will start working until `loop.run` is called, and the loop is automatically
destroyed once it's execution ends, that is, when `run` returns.


Tasks
-----

The cooperative task abstraction provided by flubber (though the :class:`Task` class).
The public API for this class mimics that of a `threading.Thread` thread, but it's
scheduled cooperatively.

Currently tasks are implemented using the `greenlet` library, however this may change
in the future.

Here are some 'rules' that apply to tasks:

- Tasks don't yield control to each other, they must always yield control to the loop,
  or schedule a switch to the desired task in the loop, this ensures predictable
  execution order and fairness
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

    flubber.sleep(0)

The only functions that suspend the current task are those which 'block', for example lock or
socket functions.

