
.. module:: flubber.net

Utilities for network servers
=============================

The net module provides some convenience functions to write network clients and servers
in an easy and compact way.

.. note::
    This module is pretty experimental, it will probably experiment lots of changes.


.. py:function:: connect(endpoint, [source_address])

    Convenience function for opening client sockets.
    
    :param endpoint: Endpoint address to connect to. TCP, UDP and UNIX sockets are supported. Examples:

    - tcp:127.0.0.1:1234
    - udp:127.0.0.1:1234
    - unix:/tmp/foo.sock

    :param source_address: Local address to bind to, optional.
    :return: The connected socket object


.. py:function:: listen(endpoint, [backlog])

    Convenience function for opening server sockets.
    
    :param endpoint: Endpoint address to listen on. TCP, UDP and UNIX sockets are supported. Examples:
    
    - tcp:127.0.0.1:1234
    - udp:127.0.0.1:1234
    - unix:/tmp/foo.sock

    :param backlog: The maximum number of queued connections. Should be at least 1, the maximum value
        is system-dependent.
    :return: The listening socket object.

    .. note::
        Sets SO_REUSEADDR on the socket to save on annoyance.

