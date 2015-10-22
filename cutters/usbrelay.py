# Copyright (c) 2015 Intel, Inc.
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
Tool for handling Usbrelay USB Cutter devices.
"""

import re
import time
import logging
import os
import subprocess
from collections import namedtuple

from aft.cutter import Cutter

UsbrelayTypes = \
    namedtuple("USBRELAY_TYPES",
               "version cutter_type channels")


class Usbrelay(Cutter):
    """
    Wrapper for controlling cutters from Usbrelay.
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
        
        if not super(Usbrelay , cls).init_class(command="bash",timeout=10):
            return False
        cls._types.append(
             UsbrelayTypes(version=1,cutter_type="USB",channels=2))

        return cls._probe_cutters() and \
            cls._allocate_channels()

    @classmethod
    def _get_type(cls, version):
        """
        Returns a handler for a UsbrelayCutter type,
        based on the version number.
        """
        for cutter_type in cls._types:
            if int(cutter_type.version) == int(version):
                return cutter_type
        return None

    @classmethod
    def run(cls, parms=()):
        """
        Execute the cutter tool with custom parameters.
        """
        return cls._run(parms)  # execute only once

    def run_on_self(self, parms=()):
        """
        Execute the cutter tool with custom parameters.
        """
        return subprocess.call(["python", os.path.join(os.path.dirname(__file__), 
                                         os.path.pardir, "tools",
                                         "cutter_on_off.py"), 
                                         self._cutter_id, parms[0]])

    @classmethod
    def _probe_cutters(cls):
        """
        Detects the characteristics of each cutter device
        connected to the host PC.
        """
        logging.info("Detecting cutters connected.")
        result = subprocess.check_output(["python", os.path.join(os.path.dirname(__file__),
                                             os.path.pardir, "tools",
                                             "list_cutters.py")])
        if result == "" :
            logging.critical("Failed detecting the cutters attached.")
            return False
        cmd_output = result.split("\n")
        if not cmd_output:
            logging.critical("Failure detecting Usbrelay cutters.\n")
            return False
        logging.info("list usbrelay:{0}".format(cmd_output))
        cutters = []
        for d in cmd_output:
            if d:
                version,cutter_id = d.split()
                cutter = Usbrelay(version=version, cutter_id=cutter_id)
                cutters.append(cutter)
            else:
                continue
        cls._cutters = cutters
        logging.info("Detection of Usbrelay cutters complete.")
        return True

    @classmethod
    def get_channel_by_id_and_cutter_id(cls, cutter_id, channel_id):
        """
        Returns the channel with channel_id which belongs to cutter_id.
        """
        logging.info("List channels:{0}".format(cls._channels))
        for channel in cls._channels:
            logging.info("Channel id: {0} Cutter id: {1}".format(channel.get_id(),channel.get_cutter().get_id()))
            if int(channel.get_id()) == int(channel_id) and \
               str(channel.get_cutter().get_id()) == str(cutter_id):
                return channel
        return None

    def _set_channel_connected_state(self, channel_id, connected):
        """
        Method to open/close a cutter channelfor cleware cutters.
        """
        if connected :
           action = '1'
        else:
           action = '0'
        result = self.run_on_self((action ,))

        if result != 0 :
             ret = False
        else:
             ret = True
        return ret

    @classmethod
    def _set_con_stat_all_chan_type(cls, cutter_type, connected):
        """
        Method to set the connected state for all the channels
        of a specified type.
        """
        for cutter in cls._cutters:
            if str(cutter.cutter_type.cutter_type) == str(cutter_type):
                for channel_id in range(cutter.cutter_type.channels):
                    cls._set_channel_connected_state(cutter,
                                                     channel_id=channel_id,
                                                     connected=connected)
                    return True
        return False

    @classmethod
    def connect_all_channels_of_type(cls, cutter_type):
        """
        Method to set the connected state for all the channels
        of a specified type.
        """
        return cls._set_con_stat_all_chan_type(cutter_type=cutter_type,
                                               connected=True)

    @classmethod
    def disconnect_all_channels_of_type(cls, cutter_type):
        """
        Method to set the connected state for all the channels
        of a specified type.
        """
        return cls._set_con_stat_all_chan_type(cutter_type=cutter_type,
                                               connected=False)
