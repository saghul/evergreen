===========================================
Evergreen: cooperative multitasking and i/o
===========================================

Overview
========

Evergreen is a cooperative multitasking and i/o library for Python. It provides equivalent primitives to
those for thread programming, but uses a cooperative model instead.

Operations are driven by an event loop which will run the given tasks and i/o operations in a non-blocking
manner while presenting the user a synchronous, blocking API.

Features:

- Cooperative multitasking
- Cooperative synchronization primitives: locks, events, queues, channels
- Futures API (almost) compatible with the standard library
- Cooperative versions of several standard library modules
- Ability to monkey patch standard library modules to make them
  cooperative


Running the test suite
======================

There are several ways of running the test suite:

- Running individual tests:

  Go inside the tests/ directory and run each individual test

- Run the test with the current Python interpreter:

  From the toplevel directory, run: ``nosetests -v -w tests/``

- Use Tox to run the test suite in several virtualenvs with several interpreters

  From the toplevel directory, run: ``tox -e py26,py27,py32, py33`` this will run the test suite
  on Python 2.6, 2.7, 3.2 and 3.3 (you'll need to have them installed beforehand)


CI status
=========

.. image:: https://secure.travis-ci.org/saghul/evergreen.png?branch=master
    :target: http://travis-ci.org/saghul/evergreen


Documentation
=============

http://readthedocs.org/docs/evergreen/


Author
======

Saúl Ibarra Corretgé <saghul@gmail.com>

Code written by other authors has been adapted for use with Evergreen, check
the NOTICE file.


License
=======

Unless stated otherwise on-file Evergreen uses the MIT license, check LICENSE and NOTICE files.


Contributing
============

If you'd like to contribute, fork the project, make a patch and send a pull
request. Have a look at the surrounding code and please, make yours look
alike :-) If you intend to contribute a new feature please contact the maintainer
beforehand in order to discuss the design.

