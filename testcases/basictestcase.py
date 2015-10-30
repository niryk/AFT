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
import subprocess32

from aft.testcase import TestCase


# pylint: disable=no-init
class BasicTestCase(TestCase):
    """
    Simple Test Case executor.
    """

    def __init__(self, config):
        super(BasicTestCase, self).__init__(config)
        self.output = None
        self.parameters = config["parameters"]
        self.pass_regex = config["pass_regex"]

    def run_local_command(self, device):
        """
        Executes a command locally, on the test harness.
        """
        process = subprocess32.Popen(self.parameters.split(), universal_newlines=True, stderr=subprocess32.STDOUT, stdout=subprocess32.PIPE)
        self.output = process.communicate()[0]
        return True

    def run_remote_command(self, device):
        """
        Executes a command remotely, on the device.
        """
        self.output = device.execute(
            command=tuple(self["parameters"].split()),
            timeout=120, )
        logging.debug("Command: {0}\nresult: {1}".
                      format(self.parameters, self.output))
        return self._check_for_success()

    def _check_for_success(self):
        """
        Test for success.
        """
        logging.info("self.output " + self.output)
        if self.output == None or self.output.returncode != 0:
            logging.info("Test Failed: returncode {0}"
                         .format(self.output.returncode))
            if self.output != None:
              logging.info("stdout:\n{0}".format(self.output.stdoutdata))
              logging.info("stderr:\n{0}".format(self.output.stderrdata))
        elif self.pass_regex == "":
            logging.info("Test passed: returncode 0, no pass_regex")
            return True
        else:
            for line in self.output.stdoutdata.splitlines():
                if re.match(self.pass_regex, line) != None:
                    logging.info("Test passed: returncode 0 "
                                 "Matching pass_regex {0}"
                                 .format(self["pass_regex"]))
                    return True
            else:
                 logging.info("Test failed: returncode 0\n"
                              "But could not find matching pass_regex {0}"
                              .format(self["pass_regex"]))
        return False

# pylint: enable=no-init
