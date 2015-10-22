# Copyright (c) 2013, 2014, 2015 Intel, Inc.
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
Tool for handling Cleware USB Cutter devices.
"""

import re
import time
import logging
from collections import namedtuple

from aft.cutter import Cutter

ClewareCutterTypes = \
    namedtuple("CLEWARE_CUTTER_TYPES",
               "version cutter_type channels opening_value closing_value "
               "opening_transient closing_transient")


class ProxyCutter(Cutter):
    """
    Wrapper for controlling cutters from Cleware Gmbh.
    """
    def __init__(self, version, cutter_id):
        self.cutter_type = self._get_type(version)
        self._cutter_id = cutter_id

    def get_id(self):
        """
        Returns the cutter_id.
        """
        return self._cutter_id

    @classmethod
    def init(cls):
        """
        Init method for class variables.
        """
        return True

    @classmethod
    def _get_type(cls, version):
        """
        Returns a handler for a ClewareCutter type,
        based on the version number.
        """
        return 1

    @classmethod
    def run(cls, parms=()):
        """
        Execute the cutter tool with custom parameters.
        """
        return True  # execute only once

    def run_on_self(self, parms=()):
        """
        Execute the cutter tool with custom parameters.
        """
        return True

    @classmethod
    def _probe_cutters(cls):
        return True

    @classmethod
    def get_channel_by_id_and_cutter_id(cls, cutter_id, channel_id):
        """
        Returns the channel with channel_id which belongs to cutter_id.
        """
        return ProxyChannel()

    def _set_channel_connected_state(self, channel_id, connected):
        """
        Method to open/close a cutter channelfor cleware cutters.
        """
        return True

    @classmethod
    def _set_con_stat_all_chan_type(cls, cutter_type, connected):
        """
        Method to set the connected state for all the channels
        of a specified type.
        """
        return True

    @classmethod
    def connect_all_channels_of_type(cls, cutter_type):
        """
        Method to set the connected state for all the channels
        of a specified type.
        """
        return True

    @classmethod
    def disconnect_all_channels_of_type(cls, cutter_type):
        """
        Method to set the connected state for all the channels
        of a specified type.
        """
        return True

class ProxyChannel(object):
    def connect(self):
        """
        Connect the device.
        """
        return True

    def disconnect(self):
        """
        Disconnect the device.
        """
        return True
