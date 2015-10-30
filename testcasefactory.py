# Copyright (c) 2013, 2014, 2015 Intel, Inc.
# Author topi.kuutela@intel.com
#
# This program is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the
# Free Software Foundation; version 2 of the License
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
# See the GNU General Public License for more details.

import aft.testcases.linuxtestcase
import aft.testcases.basictestcase
import aft.testcases.qatestcase
import aft.testcases.unixtestcase

_test_cases = {
    "qatestcase" : aft.testcases.qatestcase.QATestCase,
    "unixtestcase" : aft.testcases.unixtestcase.UnixTestCase,
    "basictestcase" : aft.testcases.basictestcase.BasicTestCase,
    "linuxtestcase" : aft.testcases.linuxtestcase.LinuxTestCase,
}

def build_test_case(parameters):
	return _test_cases[parameters["test_case"]](parameters)