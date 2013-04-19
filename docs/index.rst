
Evergreen: cooperative i/o and multitasking for Python
======================================================

Overview
--------

Evergreen is a Python library to help you write multitasking and i/o driven
applications in a cooperative way. Unlike when using threads, where the
execution model is preemptive and thus not controlled by *you*, using a
cooperative model allows you to choose *what* runs and *when*.
Evergreen will make this easier.


Features
--------

* Cooperative multitasking abstractions similar to threads
* Multiple synchronization primitives
* Event loop driven scheduler
* Non-blocking i/o
* Convenience APIs for writing network server software
* Cooperative `concurrent.futures` style APIs
* Cooperative versions of certain standard library modules
* As little magic as possible


Documentation
-------------

.. toctree::
   :maxdepth: 3
   :titlesonly:

   design
   api
   examples


Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

