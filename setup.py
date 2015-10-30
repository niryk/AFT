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

import os
from setuptools import setup

config_files = ["config/platform.cfg",
                "config/catalog.cfg",
                "config/topology.cfg"]
test_plans = ["test_plan/iot_qatest.cfg"]

config_filter = lambda file : not os.path.isfile(os.path.join("/etc/aft", file))
config_files = filter(config_filter, config_files)
test_plans = filter(config_filter, test_plans)

setup(
    name = "aft",
    version = "1.0.0a2",
    description = "Automated Flasher Tester 2",
    author = "Igor Stoppa & Topi Kuutela",
    author_email = "igor.stoppa@intel.com & topi.kuutela@intel.com",
    url = "github",
    packages = ["aft"],
    package_dir = {"aft" : "."},
    package_data = {
                    "aft" : ["cutters/*.py",
                             "devices/*.py", "devices/data/*",
                             "testcases/*.py",
                             "tools/*.py"]
                    },
    install_requires = ["netifaces", "subprocess32"],
    entry_points = { "console_scripts" : ["aft=aft.main:main"] },
    data_files = [
                  ("/etc/aft/config/", config_files),
                  ("/etc/aft/test_plan/", test_plans)
                  ]
      )
