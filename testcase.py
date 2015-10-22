# Copyright (c) 2013, 2014, 2015 Intel, Inc.
# Author Antti Kervinen <antti.kervinen@intel.com>
# Rearranged by igor.stoppa@intel.com
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
Class representing a Test Case.
"""


import os
import re
import datetime
import logging

VERSION = "0.1.0"


# Disable "Too few public methods."
# This class is meant to perform one single task
# and therefore requires only one public method
# pylint: disable=too-few-public-methods
class TestCase(dict):
    """
    Class providing the foundations for a Test Case.
    """

    _TEST_EXEC_ROOT = os.getenv("AFT_EXECROOT", "./aft_results.")

# pylint: disable=too-many-arguments
    def __init__(self, name, test, parameters, pass_regex, user):
        super(TestCase, self).__init__()
        self["name"] = name
        self["test"] = test
        self["parameters"] = parameters
        self["pass_regex"] = pass_regex
        self["user"] = user
        self["result"] = None
        self["env"] = None
        self["duration"] = None
        self["output"] = None
        self["xunit_section"] = ""
        self["test_dir"] = None
        self["device"] = None
        self["start_time"] = 0
        self["end_time"] = 0
# pylint: enable=too-many-arguments

    @staticmethod
    def _is_test_case(entry):
        """
        Method that subclasses can re-define, for sieving test cases
        out of a directory structure.
        Takes as input the name of the file, with full path.
        The default version tests if the file is executable.
        """
        return os.access(entry, os.X_OK)

    def _prepare_test_env(self):
        """
        Prepares a dictionary containing environment for test execution
        """
        self["env"] = []
        return True

    def _prepare_test_dir(self):
        """
        Prepare a directory for the test case and return its name.
        """
        date = datetime.datetime.now().strftime("%Y%m%d%H%M%S%f")
        test_dir = os.path.join(self._TEST_EXEC_ROOT + str(os.getpid()),
                                "%s-%s" % (date, self["name"]))
        os.makedirs(test_dir)
        os.makedirs(os.path.join(test_dir, "aft"))
        self["test_dir"] = test_dir

    def _prepare(self):
        """
        Preliminary setup, performed before each test case.
        """
        self._prepare_test_dir()
        return self._prepare_test_env()

    def _build_xunit_section(self):
        """
        Generates the section of report specific to the current
        test case.
        Can be overloaded by subclasses reporting more information.
        """
        xml = []
        xml.append('<testcase name="{0}" '
                   'passed="{1}" '
                   'duration="{2}">'.
                   format(self["name"],
                          '1' if self["result"] else '0',
                          self["duration"]))
        if not self["result"]:
            xml.append(('\n<failure message="test failure">\n'
                        '{0}\n</failure>\n'.format(self["output"])))
        xml.append('</testcase>\n')
        self["xunit_section"] = "".join(xml)
        return True

    def _check_for_success(self):
        """
        Checks if any of the output lines matches
        the regex that identifies a succesfull run.
        """
        self["result"] = False
        logging.info("self['output'] {0}".format(self["output"]))
        if self["output"] is None or self["output"].returncode is not 0:
            logging.info("Test Failed: returncode {0}"
                         .format(self["output"].returncode))
            if self["output"] is not None:
              logging.info("stdout:\n{0}".format(self["output"].stdoutdata))
              logging.info("stderr:\n{0}".format(self["output"].stderrdata))
        elif self["pass_regex"] is "":
            logging.info("Test passed: returncode 0, no pass_regex")
            self["result"] = True
        else:
            for line in self["output"].stdoutdata.splitlines():
                if re.match(self["pass_regex"], line) is not None:
                    logging.info("Test passed: returncode 0 "
                                 "Matching pass_regex {0}"
                                 .format(self["pass_regex"]))
                    self["result"] = True
                    break
            else:
                 logging.info("Test failed: returncode 0\n"
                              "But could not find matching pass_regex {0}"
                              .format(self["pass_regex"]))
        return self["result"]

    def execute(self, device):
        """
        Prepare and executes the test case, storing the results.
        Run the test cases.
        """
        self["device"] = device
        self["start_time"] = datetime.datetime.now()
        logging.info("Test Start Time: {0}".format(self["start_time"]))
        self._prepare()
        getattr(self, self["test"])()
        self["duration"] = datetime.datetime.now() - self["start_time"]
        logging.info("Test Duration: {0}".format(self["duration"]))
        self._build_xunit_section()
        return True


# pylint: enable=too-few-public-methods
