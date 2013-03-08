
.. module:: flubber.patcher

Monkeypatching support
======================

Flubber supports monkeypatching certain modules to make them cooperative. By monkeypatching,
some modules which block are replaced with API compatible versions which cooperatively yield.

While flubber doesn't encourage this practice, because it leads to unexpected behavior depending
on how modules are used, limited support is provided for some common modules:

- socket
- select
- time
- subprocess (broken at the moment)

This module provides several functions to monkeypatch modules.


.. py:function:: patch(**modules)

    Globally patches the given modules to make them cooperative. Example:

    ::

        import flubber.patcher

        patcher.patch(socket=True, select=True, time=True)


.. py:function:: is_patched(module)

    Returns true if the given module is currently monkeypatched, false otherwise.
    *Module* can be either the module object ot its name.


.. py:function:: import_patched(module, **additional_modules)

    Imports a module and ensures that it uses the cooperative versions of the specified
    modules, or all of the supported ones in case no `additional_modules` is supplied.
    Example:

    ::

        import flubber.patcher

        SocketServer = patcher.import_patched('SocketServer')


.. py:function:: original(module)

    Returns an un-patched version of a module.


