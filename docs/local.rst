
.. module:: evergreen.local

Task local storage
==================

This module provides the equivalent to `threading.local` but applying
the concept to tasks.


.. py:class:: local

    A class that represents task-local data.  Task-local data are data whose
    values are task specific. To manage task-local data, just create an
    instance of :class:`local` (or a subclass) and store attributes on it
    
    ::
 
       mydata = local()
       mydata.x = 1
 
    The instance's values will be different for separate tasks.
 
