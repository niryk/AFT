# Copyright (c) 2013-14 Intel, Inc.
# Author igor.stoppa@intel.com
#
# This program is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the
# Free Software Foundation; version 2 of the License
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
# See the GNU General Public License for more details.

"""
Base class for Cutter devices.
"""

import abc
from aft.cmdlinetool import CmdLineTool


# pylint: disable=no-init
class Cutter(CmdLineTool):
    """
    Common abstract base class for all the makes of cutters.
    """
    DEFAULT_TIMEOUT = 5
    __metaclass__ = abc.ABCMeta

    @classmethod
    def init_class(cls, command=None, timeout=DEFAULT_TIMEOUT,
                   exit_on_error=False):
        """
        Init method for class variables.
        """
        cls._types = []
        cls._cutters = []
        cls._channels = []
        return super(Cutter, cls).init_class(command=command,
                                             timeout=timeout,
                                             exit_on_error=exit_on_error)

    @classmethod
    @abc.abstractmethod
    def _probe_cutters(cls):
        """
        Detects the characteristics of each cutter device
        connected to the host PC.
        """

    @classmethod
    def get_channels(cls):
        """
        Retruns handle to all detected channels.
        """
        return cls._channels

    @classmethod
    def _allocate_channels(cls):
        """
        Creates handlers for each channel in each cutter.
        """
        channels = []
        for cutter in cls._cutters:
            for channel_id in range(cutter.cutter_type.channels):
                channels.append(CutterChannel(cutter=cutter,
                                              channel_id=channel_id))
        cls._channels = channels
        return True

    @classmethod
    @abc.abstractmethod
    def get_channel_by_id_and_cutter_id(cls, cutter_id, channel_id):
        """
        Returns the channel with channel_id which belongs to cutter_id
        """

    @abc.abstractmethod
    def _set_channel_connected_state(self, channel_id, connected):
        """
        Method programming the state of a channel
        """

    def connect_channel(self, channel_id):
        """
        Method connecting a channel
        """
        return self._set_channel_connected_state(channel_id=channel_id,
                                                 connected=True)

    def disconnect_channel(self, channel_id):
        """
        Method disconnecting a channel
        """
        return self._set_channel_connected_state(channel_id=channel_id,
                                                 connected=False)
# pylint: enable=no-init


class CutterChannel(object):
    """
    Cutters have variable number of channels,
    depending on the type. This is one.
    """
    def __init__(self, cutter, channel_id):
        self._channel_id = channel_id
        self._cutter = cutter

    def get_id(self):
        """
        Return the id of the chennel.
        """
        return self._channel_id

    def get_cutter(self):
        """
        Return the cutter the channel belongs to.
        """
        return self._cutter

    def connect(self):
        """
        Connect the device.
        """
        return self._cutter.connect_channel(channel_id=self._channel_id)

    def disconnect(self):
        """
        Disconnect the device.
        """
        return self._cutter.disconnect_channel(channel_id=self._channel_id)
