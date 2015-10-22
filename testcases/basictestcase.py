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
Basic Test Case class.
"""
import logging
import subprocess

from aft.testcase import TestCase


# pylint: disable=no-init
class BasicTestCase(TestCase):
    """
    Simple Test Case executor.
    """

    def run_local_command(self):
        """
        Executes a command locally, on the test harness.
        """
        process = subprocess.Popen(self["parameters"].split(), universal_newlines=True, stderr=subprocess.STDOUT, stdout=subprocess.PIPE)
        self["output"] = process.communicate()[0]
        return True

    def run_remote_command(self):
        """
        Executes a command remotely, on the device.
        """
        self["output"] = self["device"].execute(
            command=tuple(self["parameters"].split()),
            timeout=120, )
        logging.debug("Command: {0}\nresult: {1}".
                      format(self["parameters"], self["output"]))
        return self._check_for_success()
# pylint: enable=no-init
