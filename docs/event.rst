
.. module:: flubber.event

Synchronization primitives: Event
=================================

This is one of the simplest mechanisms for communication between tasks: one
task signals an event and other threads wait for it.


.. py:class:: Event

    This class implements a cooperative version of `threading.Event`.

    .. py:method:: is_set

        Returns `True` if the flag is set, `False` otherwise.

    .. py:method:: set

        Set the internal flag to true. All tasks waiting for it to become true are awakened.
        Tasks that call wait() once the flag is true will not block at all.

    .. py:method:: clear

        Reset the internal flag to false. Subsequently, tasks calling wait() will block
        until set() is called to set the internal flag to true again.

    .. py:method:: wait([timeout])

        Block until the internal flag is true. If the internal flag is true on entry,
        return immediately. Otherwise, block until another task calls set() to set the
        flag to true, or until the optional timeout occurs. The internal flag is returned
        on exit.

