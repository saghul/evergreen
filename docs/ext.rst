
.. module:: flubber.ext

Extending flubber
=================

Flubber provides a friendly way to import extensions that users may implement.
This mechanism has been borrowed from Flask :-)

There are no rules in how modules should be named, but if your module happens
to be named `flubber-foo` you can import the module like this

::

    from flubber.ext import foo

instead of doing

::

    import flubber_foo


