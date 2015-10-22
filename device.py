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
Class representing a DUT.
"""


import abc
from aft.tester import Tester

VERSION = "0.1.0"


class Device(object):
    """
    Abstract class representing a DUT.
    """
    __metaclass__ = abc.ABCMeta

    def __init__(self, device_descriptor, channel):
        self.name = device_descriptor["name"]
        self.model = device_descriptor["model"]
        self.dev_id = device_descriptor["id"]
        self.channel = channel
        self.catalog_entry = device_descriptor["catalog_entry"]

    @abc.abstractmethod
    def is_in_test_mode(self):
        """
        Check if the device is in test mode.
        """

    @abc.abstractmethod
    def is_in_service_mode(self):
        """
        Check if the device is in service mode.
        """

    @abc.abstractmethod
    def write_image(self, file_name):
        """
        Writes the specified image to the device.
        """

    def test(self):
        """
        Runs the tests associated with the specified image.
        """
        return Tester.test(device=self)

    def detach(self):
        """
        Open the associated cutter channel.
        """
        return self.channel.disconnect()

    def attach(self):
        """
        Close the associated cutter channel.
        """
        return self.channel.connect()

    @abc.abstractmethod
    def execute(self, command, timeout, user="root", verbose=False):
        """
        Runs a command on the device and returns log and errorlevel.
        """

    @abc.abstractmethod
    def push(self, local_file, remote_file, user="root"):
        """
        Deploys a file from the local filesystem to the device (remote).
        """

    @abc.abstractmethod
    def get_ip(self):
        """
        Return IP-address of the active device as a String.
        """
#    @abc.abstractmethod
#    def pull(self, remote_file, local_file, user="root"):
#        """
#        Fetches a file from the device (remote) to the local filesystem.
#        """

    def __eq__(self, comp):
        return self.dev_id == comp.dev_id

    def __ne__(self, comp):
        return self.dev_id != comp.dev_id

    def __repr__(self):
        return "Device(name={0}, model={1}, dev_id={2}, channel={3}". \
            format(self.name, self.model, self.dev_id, self.channel)
