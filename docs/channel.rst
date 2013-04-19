
.. module:: evergreen.channel

Synchronization primitives: Channel
===================================

Channels are the simples mechanism for 2 tasks to exhcnage data.


.. py:class:: Channel

    A synchronous communication pipe between 2 tasks.

    .. py:method:: send(data)

        Send data over the channel. The calling task will be blocked if
        there is no task waiting for the data on the other side.

    .. py:method:: send_exception(exc_type, exc_value=None, exc_tb=None)

        Send the given exception. It will be raised on the receiving task.

    .. py:method:: receive

        Wait for data to arrive on the channel.

