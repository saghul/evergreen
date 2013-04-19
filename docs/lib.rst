
.. module:: evergreen.lib

Standard library compatible cooperative modules
===============================================

This module contains several API compatible and cooperative modules with some
standard Python library modules.

Only a subset of those is provided and it's **not** evergreen's intention to eventually
provive alternatives to every module in the standard library.

Provided modules:

- socket
- select
- time

::

    from evergreen.lib import socket

    # use the socket as it was a 'normal' one
    ...

