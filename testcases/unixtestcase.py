# Copyright (c) 2013 Intel, Inc.
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
Unix Test Case class.
"""

from aft.testcases.basictestcase import BasicTestCase


# pylint: disable=R0904
class UnixTestCase(BasicTestCase):
    """
    Unix Test Case executor.
    """
    _PROCESS_TEST_TIMEOUT = 10

    def process_is_running(self):
        """
        Checks if the specified process is running.
        """
        self["output"] = self["device"].execute(
            command=('ps', 'auxf', '|', 'grep', '-E', '"/' +
                     self["parameters"] + ' "', '|', 'grep', '-v', 'grep'),
            timeout=self._PROCESS_TEST_TIMEOUT, )
        return self._check_for_success()
# pylint: enable=R0904
