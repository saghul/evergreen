
.. module:: flubber.io

I/O utilities
=============

The io module provides utility classes for writing cooperative servers and clients
in an easy way.

.. note:: This module is still very experimental.


.. py:class:: BaseStream()

    Basic class for defining a stream-like transport.

    .. py:attribute:: readable

        Returns True if the stream can be read from, False otherwise.

    .. py:attribute:: writable

        Returns True if the stream can be written to, False otherwise.

    .. py:attribute:: closed

        Returns True if the stream is closed, False otherwise. Once the stream is closed
        an exception will be raised if any operation is attempted.

    .. py:method:: read_bytes(nbytes)

        Read the specified amount of bytes (at most) from the stream.

    .. py:method:: read_until(delimiter)

        Read until the specified delimiter is found.

    .. py:method:: read_until_regex(regex)

        Read until the given regular expression is matched.

    .. py:method:: write(data)

        Write data on the stream

    .. py:method:: close

        Close the stream. All further operations will raise an exception.

    .. py:method:: _set_connected

        This method is part of the internap API. It sets the stream state to connected. Before a
        stream is connected all write operations will be buffered and flushed once the stream
        is connected.


.. py:class:: StreamServer

    Base class for writing servers which use a stream-like transport.

    .. py:method:: bind(address)

        Bind the server to the specified address. The address will be different depending on the
        particular server implementation.

    .. py:method:: serve([backlog])

        Start listening for incoming connections. The caller will block until the server is stopped
        with a call to close.

    .. py:method:: close

        Close the server. All active connections are also closed.

    .. py:method:: handle_connection(connection)

        Abstract method which subclasses need to implement in order handle incoming connections.

    .. py:attribute:: connections

        LIst of currently active connections.


.. py:class:: StreamConnection()

    Base class representing a connection handled by a *StreamServer*.

    .. py:attribute:: server

        Reference to the *StreamServer* which accepted the connection.

    .. py:method:: close

        Close the connection.

    .. py:method:: _set_accepted(server)

        Internal API method: sets the connection state to accepted.


.. py:exception:: StreamError

    Base class for stream related errors.


.. py:class:: TCPClient()

    Class representing a TCP client.

    .. py:attribute:: sockname

        Returns the local address.

    .. py:attribute:: peername

        Returns the remote endpoint's address.

    .. py:method:: connect(target, [source_address])

        Start an outgoing connection towards the specified target. If *source_address* is
        specified the socket will be bound to it, else the system will pick an appropriate one.


.. py:class:: TCPServer()

    Class representing a TCP server.

    .. py:attribute:: sockname

        Returns the local address where the server is listening.


.. py:class:: TCPConnection()

    Class representing a TCP connection handled by a TCP server.

    .. py:attribute:: sockname

        Returns the local address.

    .. py:attribute:: peername

        Returns the remote endpoint's address.


.. py:exception:: TCPError

    Class for representing all TCP related errors.


.. py:class:: PipeClient()

    Class representing a named pipe client.

    .. py:method:: connect(target)

        Connects to the specified named pipe.


.. py:class:: PipeServer()

    Class representing a named pipe server.

    .. py:attribute:: pipename

        Returns the name of the pipe to which the server is bound.


.. py:class:: PipeConnection()

    Class representing a connection to a named pipe server.


.. py:exception:: PipeError

    Class for representing all Pipe related errors.


.. py:class:: TTYStream(fd, readable)

    Class representing a TTY stream. The specified *fd* is opened as a TTY, so make
    sure it's already a TTY. If you plan on reading from this stream specify *readable* as
    True.

    .. py:attribute:: winsize

        Returns the current window size.


.. py:class:: StdinStream()

    Convenience class to use stdin as a cooperative stream.


.. py:class:: StdoutStream()

    Convenience class to use stdout as a cooperative stream.


.. py:class:: StderrStream()

    Convenience class to use stderr as a cooperative stream.


.. py:exception:: TTYError

    Class for representing all TTY related errors.


