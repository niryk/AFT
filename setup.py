import os
from setuptools import setup

config_files = ["config/platform.cfg",
                "config/iot_catalog.cfg",
                "config/iot_topology.cfg"]
test_plans = ["test_plan/iot_qatest_test_plan.cfg"]

config_filter = lambda file : not os.path.isfile(os.path.join("/etc/aft", file))
config_files = filter(config_filter, config_files)
test_plans = filter(config_filter, test_plans)

setup(
    name = "aft",
    version = "1.0.0a",
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
    install_requires = ["netifaces"],
    entry_points = { "console_scripts" : ["aft=aft.main:main"] },
    data_files = [
                  ("/etc/aft/config/", config_files),
                  ("/etc/aft/test_plan/", test_plans)
                  ]
      )
