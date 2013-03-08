
.. module:: flubber.locks

Synchronization primitives: locks
=================================

This module implements synchronization primitives to be used with cooperative tasks,
in an analogous and API compatible way as `threading` module's primitives which are
used with threads.


.. py:class:: Semaphore([value])

    A semaphore manages an internal counter which is decremented by each
    :meth:`acquire` call and incremented by each :meth:`release` call.  The counter
    can never go below zero; when :meth:`acquire` finds that it is zero, it blocks,
    waiting until some other task calls :meth:`release`.

    The optional argument gives the initial *value* for the internal counter; it
    defaults to ``1``. If the *value* given is less than 0, :exc:`ValueError` is
    raised.

    .. py:method:: acquire([blocking])

       Acquire a semaphore.
 
       When invoked without arguments: if the internal counter is larger than
       zero on entry, decrement it by one and return immediately.  If it is zero
       on entry, block, waiting until some other task has called
       :meth:`release` to make it larger than zero. This is done with proper
       interlocking so that if multiple :meth:`acquire` calls are blocked,
       :meth:`release` will wake exactly one of them up. The implementation may
       pick one at random, so the order in which blocked tasks are awakened
       should not be relied on. Returns true (or blocks indefinitely).
 
       When invoked with *blocking* set to false, do not block.  If a call
       without an argument would block, return false immediately; otherwise, do
       the same thing as when called without arguments, and return true.
 
       When invoked with a *timeout* other than None, it will block for at
       most *timeout* seconds. If acquire does not complete successfully in
       that interval, return false.  Return true otherwise.

    .. py:method:: release()

        Release a semaphore, incrementing the internal counter by one. When it
        was zero on entry and another task is waiting for it to become larger
        than zero again, wake up that task.


.. py:class:: BoundedSemaphore([value])

    Class implementing bounded semaphore objects.  A bounded semaphore checks to
    make sure its current value doesn't exceed its initial value.  If it does,
    :exc:`ValueError` is raised. In most situations semaphores are used to guard
    resources with limited capacity.  If the semaphore is released too many times
    it's a sign of a bug. If not given, *value* defaults to 1.


.. py:class:: RLock

    This class implements reentrant lock objects. A reentrant lock must be
    released by the task that acquired it. Once a task has acquired a
    reentrant lock, the same task may acquire it again without blocking; the
    task must release it once for each time it has acquired it.

    .. py:method:: acquire(blocking=True, timeout=None)
 
        Acquire a lock, blocking or non-blocking.
  
        When invoked without arguments: if this task already owns the lock, increment
        the recursion level by one, and return immediately.  Otherwise, if another
        task owns the lock, block until the lock is unlocked.  Once the lock is
        unlocked (not owned by any task), then grab ownership, set the recursion level
        to one, and return.  If more than one task is blocked waiting until the lock
        is unlocked, only one at a time will be able to grab ownership of the lock.
        There is no return value in this case.
  
        When invoked with the *blocking* argument set to true, do the same thing as when
        called without arguments, and return true.
  
        When invoked with the *blocking* argument set to false, do not block.  If a call
        without an argument would block, return false immediately; otherwise, do the
        same thing as when called without arguments, and return true.
  
        When invoked with the floating-point *timeout* argument set to a positive
        value, block for at most the number of seconds specified by *timeout*
        and as long as the lock cannot be acquired.  Return true if the lock has
        been acquired, false if the timeout has elapsed.
 
    .. py:method:: release
 
        Release a lock, decrementing the recursion level.  If after the decrement it is
        zero, reset the lock to unlocked (not owned by any task), and if any other
        tasks are blocked waiting for the lock to become unlocked, allow exactly one
        of them to proceed.  If after the decrement the recursion level is still
        nonzero, the lock remains locked and owned by the calling task.
  
        Only call this method when the calling task owns the lock. A
        :exc:`RuntimeError` is raised if this method is called when the lock is
        unlocked.
  
        There is no return value.


.. py:class:: Condition(lock=None)

    This class implements condition variable objects.  A condition variable
    allows one or more tasks to wait until they are notified by another task.

    If the *lock* argument is given and not ``None``, it must be a :class:`Semaphore`
    or :class:`RLock` object, and it is used as the underlying lock.  Otherwise,
    a new :class:`RLock` object is created and used as the underlying lock.

    .. py:method:: acquire(\*args)
 
        Acquire the underlying lock. This method calls the corresponding method on
        the underlying lock; the return value is whatever that method returns.
 
    .. py:method:: release()
 
        Release the underlying lock. This method calls the corresponding method on
        the underlying lock; there is no return value.
 
    .. py:method:: wait(timeout=None)
 
        Wait until notified or until a timeout occurs. If the calling task has
        not acquired the lock when this method is called, a :exc:`RuntimeError` is
        raised.
  
        This method releases the underlying lock, and then blocks until it is
        awakened by a :meth:`notify` or :meth:`notify_all` call for the same
        condition variable in another task, or until the optional timeout
        occurs.  Once awakened or timed out, it re-acquires the lock and returns.
  
        When the *timeout* argument is present and not ``None``, it should be a
        floating point number specifying a timeout for the operation in seconds
        (or fractions thereof).
  
        When the underlying lock is an :class:`RLock`, it is not released using
        its :meth:`release` method, since this may not actually unlock the lock
        when it was acquired multiple times recursively.  Instead, an internal
        interface of the :class:`RLock` class is used, which really unlocks it
        even when it has been recursively acquired several times. Another internal
        interface is then used to restore the recursion level when the lock is
        reacquired.
  
        The return value is ``True`` unless a given *timeout* expired, in which
        case it is ``False``.
 
    .. method:: notify(n=1)
 
        By default, wake up one task waiting on this condition, if any.  If the
        calling task has not acquired the lock when this method is called, a
        :exc:`RuntimeError` is raised.
  
        This method wakes up at most *n* of the tasks waiting for the condition
        variable; it is a no-op if no tasks are waiting.
  
        The current implementation wakes up exactly *n* tasks, if at least *n*
        tasks are waiting.  However, it's not safe to rely on this behavior.
        A future, optimized implementation may occasionally wake up more than
        *n* tasks.
  
        Note: an awakened task does not actually return from its :meth:`wait`
        call until it can reacquire the lock.  Since :meth:`notify` does not
        release the lock, its caller should.
 
    .. method:: notify_all
 
        Wake up all tasks waiting on this condition.  This method acts like
        :meth:`notify`, but wakes up all waiting tasks instead of one. If the
        calling task has not acquired the lock when this method is called, a
        :exc:`RuntimeError` is raised.

