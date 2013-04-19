
.. module:: evergreen.ext

Extending evergreen
===================

evergreen provides a friendly way to import extensions that users may implement.
This mechanism has been borrowed from Flask :-)

There are no rules in how modules should be named, but if your module happens
to be named `evergreen-foo` you can import the module like this

::

    from evergreen.ext import foo

instead of doing

::

    import evergreen_foo


