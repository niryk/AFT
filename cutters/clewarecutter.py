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


class ClewareCutter(Cutter):
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
        if not super(ClewareCutter, cls).init_class(command="clewarecontrol"):
            return False
        cls._types.append(
            ClewareCutterTypes(version=5, cutter_type="USB", channels=1,
                               opening_value=0, closing_value=1,
                               opening_transient=1,
                               closing_transient=3))
        cls._types.append(
            ClewareCutterTypes(version=23, cutter_type="MainsSingle",
                               channels=1, opening_value=0,
                               closing_value=1, opening_transient=3,
                               closing_transient=5))
        cls._types.append(
            ClewareCutterTypes(version=29, cutter_type="MainsQuad",
                               channels=4, opening_value=0,
                               closing_value=1, opening_transient=3,
                               closing_transient=5))
        cls._types.append(
            ClewareCutterTypes(version=51, cutter_type="MainsSingleNew",
                               channels=4, opening_value=0,
                               closing_value=1, opening_transient=3,
                               closing_transient=5))
        cls._types.append(
            ClewareCutterTypes(version=512, cutter_type="MainsQuad",
                               channels=4, opening_value=0,
                               closing_value=1, opening_transient=3,
                               closing_transient=5))

        return cls._probe_cutters() and \
            cls._allocate_channels()

    @classmethod
    def _get_type(cls, version):
        """
        Returns a handler for a ClewareCutter type,
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
        return cls._run(parms=("-c", "1",) + parms)  # execute only once

    def run_on_self(self, parms=()):
        """
        Execute the cutter tool with custom parameters.
        """
        return self._run(parms=("-d", str(self._cutter_id), "-c", "1",) + parms)

    @classmethod
    def _probe_cutters(cls):
        """
        Detects the characteristics of each cutter device
        connected to the host PC.
        """
        logging.info("Detecting cutters connected.")
        result = cls.run(parms=("-l",))
        if result is None or result.returncode is not 0:
            logging.critical("Failed detecting the cutters attached.")
            return False
        cmd_output = result.stdoutdata.split("\n")
        if not (("Cleware library version:" in cmd_output[0]) and
                ("Number of Cleware devices found:" in cmd_output[1]) and
                (cmd_output[len(cmd_output) - 1] == "")):
            logging.critical("Failure detecting Cleware cutters.\n"
                             "Unexpected output:\n{0}".format(cmd_output))
            return False
        cutters = []
        for i in range(2, len(cmd_output)):
            if "Switch1" in cmd_output[i]:  # check that it's a cutter
                # Filter to parse a string obtained while probing.
                # "Device: X, type: Switch1 (Y),
                # version: Z, serial number: S/N"
                # where X & Y are dontcare
                version, cutter_id = \
                    re.findall(r'\b\d+\b', cmd_output[i])[2:4]
                cutter = ClewareCutter(version=version, cutter_id=cutter_id)
                if cutter.cutter_type is None:
                    logging.warn("Skipping unrecognised cutter.\n{0}"
                                 .format(cmd_output[i]))
                else:
                    cutters.append(cutter)
        cls._cutters = cutters
        logging.info("Detection of Cleware cutters complete.")
        return True

    @classmethod
    def get_channel_by_id_and_cutter_id(cls, cutter_id, channel_id):
        """
        Returns the channel with channel_id which belongs to cutter_id.
        """
        for channel in cls._channels:
            if int(channel.get_id()) == int(channel_id) and \
               int(channel.get_cutter().get_id()) == int(cutter_id):
                return channel
        return None

    def _set_channel_connected_state(self, channel_id, connected):
        """
        Method to open/close a cutter channelfor cleware cutters.
        """
        result = self.run_on_self(
            parms=("-as", "{0}".format(channel_id),
                   "{0}".format(self.cutter_type.closing_value if connected 
                                else self.cutter_type.opening_value)))
        if result is not None and result.returncode is not 0:
            time.sleep(
                self.cutter_type.closing_transient if connected else
                self.cutter_type.opening_transient)
        return result

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
