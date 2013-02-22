# -*- coding: utf-8 -
#
# This file is part of flubber. See the NOTICE for more information.

from __future__ import absolute_import

import flubber
from flubber.event import Event

import select as __select__
__all__     = ['select', 'error']
__patched__ = ['select']

error = __select__.error


def get_fileno(obj):
    # The purpose of this function is to exactly replicate
    # the behavior of the select module when confronted with
    # abnormal filenos; the details are extensively tested in
    # the stdlib test/test_select.py.
    try:
        f = obj.fileno
    except AttributeError:
        if not isinstance(obj, (int, long)):
            raise TypeError("Expected int or long, got " + type(obj))
        return obj
    else:
        rv = f()
        if not isinstance(rv, (int, long)):
            raise TypeError("Expected int or long, got " + type(rv))
        return rv


class SelectHelper(object):

    def __init__(self):
        self.loop = flubber.current.loop
        self._read_fds = []
        self._write_fds = []
        self._event = Event()
        self.rlist = []
        self.wlist = []

    def add_reader(self, fdobj):
        fd = get_fileno(fdobj)
        self._read_fds.append(fd)
        self.loop.add_reader(fd, self._on_read, fdobj)

    def add_writer(self, fdobj):
        fd = get_fileno(fdobj)
        self._write_fds.append(fd)
        self.loop.add_writer(fd, self._on_write, fdobj)

    def wait(self, timeout):
        self._event.wait(timeout)

    def close(self):
        for fd in self._read_fds:
            self.loop.remove_reader(fd)
        for fd in self._write_fds:
            self.loop.remove_writer(fd)

    def _on_read(self, fdobj):
        self.rlist.append(fdobj)
        self._event.set()

    def _on_write(self, fdobj):
        self.wlist.append(fdobj)
        self._event.set()


def select(read_list, write_list, error_list, timeout=None):
    if timeout is not None:
        # error checking like this is required by the stdlib unit tests
        try:
            timeout = float(timeout)
        except ValueError:
            raise TypeError("Expected number for timeout")

    helper = SelectHelper()
    for fdobj in read_list:
        helper.add_reader(fdobj)
    for fdobj in write_list:
        helper.add_writer(fdobj)

    try:
        helper.wait(timeout)
        return helper.rlist, helper.wlist, []
    finally:
        helper.close()

