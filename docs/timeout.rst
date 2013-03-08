
.. module:: flubber.timeout

Managing timeouts
=================

Timeout objects allow to stop a task after a given amount of time. This
is useful to abort a network connection if the response is taking
too long to arrive, for example.


.. py:class:: Timeout([seconds, [exception]])

    Raises *exception* in the current task after *timeout* seconds.

    When *exception* is omitted or ``None``, the :class:`Timeout` instance
    itself is raised. If *seconds* is None or < 0, the timer is not scheduled, and is
    only useful if you're planning to raise it directly.

    :class:`Timeout` objects are context managers, and so can be used in with statements.
    When used in a with statement, if *exception* is ``False``, the timeout is
    still raised, but the context manager suppresses it, so the code outside the
    with-block won't see it.

    .. py:method:: start

        Start the Timeout object.

    .. py:method:: cancel

        Prevent the Timeout from raising, if hasn't done so yet.

