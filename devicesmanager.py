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

"""Tool for managing collection of devices from the same host PC"""

import logging
from argparse import ArgumentParser
from ConfigParser import SafeConfigParser
import re
import os
import xml.etree.ElementTree as ET
from aft.tester import Tester

import aft.devices.edisondevice
import aft.devices.edisonstopology
import aft.devices.pcdevice
import aft.devices.pcstopology
import aft.cutters.proxycutter
import aft.cutters.clewarecutter
import aft.cutters.usbrelay

VERSION = "0.1.0"


# Disable "Too few public methods."
# This class has only one high-level task to perform
# pylint: disable=too-few-public-methods
class DevicesManager(object):
    """Class handling devices connected to the same host PC"""
    __CFG_BASE_PATH = '/etc/aft/config'

    __DEFAULT_CFG_FILE_NAME = os.path.join(__CFG_BASE_PATH, "platform.cfg")

    __TOPOLOGY_CLASS_NAME_ENDING = "sTopology"
    __DEVICE_CLASS_NAME_ENDING = "Device"

    __CATALOG_BASE_PATH = __CFG_BASE_PATH
    __CATALOG_FILE_NAME_ENDING = "_catalog.cfg"

    __TOPOLOGY_BASE_PATH = __CFG_BASE_PATH
    __TOPOLOGY_FILE_NAME_ENDING = "_topology.cfg"

    __TEST_PLAN_BASE_PATH = "/etc/aft/test_plan"
    __TEST_PLAN_FILE_NAME_ENDING = "_test_plan.cfg"

    _testability = None
    _file_name = None
    _cfg_file_name = None
    _topology_class = None
    _device_class = None
    _device_init_data = None
    _cutter_class = None
    _topology_file_name = None
    _catalog_file_name = None
    _success = False

    _device_classes = {
        "edisondevice" : aft.devices.edisondevice.EdisonDevice,
        "pcdevice" : aft.devices.pcdevice.PCDevice
    }
    _topology_classes = {
        "edisonstopology" : aft.devices.edisonstopology.EdisonsTopology,
        "pcstopology" : aft.devices.pcstopology.PCsTopology
    }
    _cutter_classes = {
        "proxycutter" : aft.cutters.proxycutter.ProxyCutter,
        "clewarecutter" : aft.cutters.clewarecutter.ClewareCutter,
        "usbrelay" : aft.cutters.usbrelay.Usbrelay
    }

#    def __init__(self):
#        self.devices = []
#
#        logging.debug("Initializing  configuration file.")
#        platform_config = SafeConfigParser()
#        platform_config.read(self._cfg_file_name)
#        if config == []:
#            raise IOError("Configuration file " + self._cfg_file_name + " not found")
#        for platform in platform_config.sections():
#            platform_params = dict(config.items(section))
#            platform_name = platform_params["platform"]
#            _device_classes[platform_name].init_class(platform_params)

    @classmethod
    def _load_config(cls):
        """
        Loads the master configuration file:
        processes known parameters and leaves a dictionary
        containing the remaining parameters, which belonging
        to specific device types, for later processing.
        """
        logging.debug("Loading configuration file.")
        try:
            config = SafeConfigParser()
            if [] == config.read(cls._cfg_file_name):
                logging.critical("Error: configuration file {0} not found."
                                 .format(cls._cfg_file_name))
                return False
            for section in config.sections():
                if not re.match(config.get(section, "regex"), cls._file_name):
                    continue
                logging.info("Loading configuration for platform {0} ."
                             .format(section))

                parms = dict(config.items(section))
                del parms["regex"]

                platform = parms["platform"]
                name = platform + cls.__TOPOLOGY_CLASS_NAME_ENDING
                logging.debug("Topology name: {0}".format(name))
                cls._topology_class = cls._topology_classes[name.lower()]
                name = platform + cls.__DEVICE_CLASS_NAME_ENDING
                cls._device_class = cls._device_classes[name.lower()]
                del parms["platform"]

                cls._catalog_file_name = \
                    os.path.join(cls.__CATALOG_BASE_PATH,
                                 parms["catalog"] +
                                 cls.__CATALOG_FILE_NAME_ENDING)
                cls._topology_file_name = \
                    os.path.join(cls.__TOPOLOGY_BASE_PATH,
                                 parms["catalog"] +
                                 cls.__TOPOLOGY_FILE_NAME_ENDING)
                del parms["catalog"]

                cls._cutter_class = \
                    cls._cutter_classes[parms["cutter"].lower()]
                del parms["cutter"]

                cls._test_plan = \
                    os.path.join(cls.__TEST_PLAN_BASE_PATH,
                                 parms["test_plan"] +
                                 cls.__TEST_PLAN_FILE_NAME_ENDING)
                del parms["test_plan"]

                if not (cls._topology_class):
                    logging.critical("Loading failed. Topology_class \n"
                                     "Malformed section {0} in file {1}."
                                     .format(section, cls._cfg_file_name))
                    return False
                if not (cls._device_class):
                    logging.critical("Loading failed. _device_class\n"
                                     "Malformed section {0} in file {1}."
                                     .format(section, cls._cfg_file_name))
                    return False
                if not (cls._cutter_class):
                    logging.critical("Loading failed._cutter_class\n"
                                     "Malformed section {0} in file {1}."
                                     .format(section, cls._cfg_file_name))
                    return False
                if not (cls._test_plan):
                    logging.critical("Loading failed._test_plan\n"
                                     "Malformed section {0} in file {1}."
                                     .format(section, cls._cfg_file_name))
                    return False
                logging.info("Configuration loaded.")
                break
            else:
                logging.critical("Could not find a type of device "
                                 "compatible with the image selected {0}"
                                 .format(cls._file_name))
                return False
        except KeyError as error:
            logging.critical("Missing configuration key from configuration "
                             "file:\n{0}".format(error))
            return False
        cls._device_init_data = parms
        return True

    @classmethod
    def _generate_topology(cls):
        """
        Scan and record the layout of devices and cutters
        """
        return cls._success and \
            cls._topology_class.generate()

    @classmethod
    def _image_is_supported(cls):
        """
        Loads the topology descriptor and verifies if the image
        is supported for testing.
        """
        if not cls._success:
            logging.debug("Success already compromised:"
                          " not testing for image supported.")
        elif not cls._topology_class.load():
            logging.critical("Failed to load topology class.")
        elif not cls._topology_class.identify_model_and_type(cls._file_name):
            logging.critical("Failed to identify model and type.")
        else:
            return True
        cls._success = False
        return False

    @classmethod
    def _reserve(cls):
        """
        Loads the topology descriptor and reserves a device
        of the appropriate type and model, if available.
        """
        if not cls._success:
            logging.debug("Success already compromised:"
                          " not reserving a device.")
        elif not cls._topology_class.reserve():
            logging.critical("Failed to reserve a device")
        else:
            return True
        cls._success = False
        return False

    @classmethod
    def _write_image(cls):
        """
        Writes the image to the reserved device.
        """
        logging.info("Writing image to the test device.")
        if not cls._success:
            logging.critical("Success already compromised:"
                             " not attempting to write image.")
        elif not cls._topology_class.reserved_device:
            logging.critical("No device was reserved: aborting image write.")
        elif not cls._topology_class.reserved_device.write_image(cls._file_name):
            logging.critical("Failed to write image.")
        else:
            return True
        cls._success = False
        return False

    @classmethod
    def _test(cls):
        """
        Runs tests on the device
        """
        logging.info("Testing the image written on the device.")
        if not cls._success:
            logging.critical("Success already compromised:"
                             " not attempting to test image.")
        elif not cls._topology_class.reserved_device:
            logging.critical("No device was reserved: aborting image test.")
        elif not cls._topology_class.reserved_device.test():
            logging.critical("Failed to test image.")
        else:
            return True
        cls._success = False
        return False


    @classmethod
    def _validate(cls):
        """
        Grabs a compatible device, writes to it the image and tests it.
        """
        logging.info("Validating the image.")
        if not cls._success:
            logging.critical("Success already compromised:"
                             " not attempting to validate image.")
        elif not cls._reserve():
            logging.critical("Failed to reserve device.")
        elif not cls._write_image():
            logging.critical("Failed to write the test image to the device.")
        elif not cls._test():
            logging.critical("Failed to test the device.")
        else:
            return True
        cls._success = False
        return False

    @classmethod
    def _load_configuration_files(cls):
        """
        Performs all the initializations preceding the writing of the image
        and testing steps.
        """
        cls._success = False
        if not cls._load_config():
            logging.critical("Failed to load config file.")
            return False
        logging.debug("Loading test plan.")
        if not Tester.init(test_plan=cls._test_plan):
            logging.critical("Failed to load test plan file.")
            return False
        logging.debug("Initializing device class.")
        if not cls._device_class.init_class(init_data=cls._device_init_data):
            logging.critical("Failed to initialize device class.")
            return False
        logging.debug("Initializing topology class.")
        if not cls._topology_class.init(
               topology_file_name=cls._topology_file_name,
               catalog_file_name=cls._catalog_file_name,
               cutter_class=cls._cutter_class):
            logging.critical("Failed to initialize topology class.")
            return False
        cls._success = True
        return True

    @classmethod
    def check_test_results(cls):
    #True if everything is OK, false otherwise
        xunit_file_location = Tester.get_results_location()
        results_xml = ET.parse(xunit_file_location)
        testsuite = results_xml.getroot()
        print("errors: " + str(testsuite.get("errors")))
        print("failures: " + str(testsuite.get("failures")))
        if int(testsuite.get("errors")) != 0 or int(testsuite.get("failures")) != 0:
            return False
        return True

    @classmethod
    def run(cls):
        """
        Parse arguments and act accordingly.
        """
        E_NO_IMAGE_NAME = 1
        E_CONFIG_FILES  = 2
        E_UNTESTABLE = 3
        E_TEST_FAILED = 4
        logging.debug("Building argument parser.")
        parser = ArgumentParser()
        parser.add_argument("--testable", action="store_true",
                            default=False,
                            help="Test if a specified image is supported.")
        parser.add_argument("--cfg", action="store",
                            default=cls.__DEFAULT_CFG_FILE_NAME,
                            help="Configuration file describing "
                                 "supported platforms.")
        parser.add_argument("file_name", action="store",
                            help="Image to write: a local file, "
                                 "compatible with the supported platforms.")
        logging.debug("Parsing arguments.")
        args = parser.parse_args()
        if not hasattr(args, "file_name"):
            logging.critical("Error parsing arguments: missing image name")
            return -E_NO_IMAGE_NAME
# pylint: disable=protected-access
        cls._file_name = args.file_name
        logging.debug("SW Image file {0}.".format(cls._file_name))
        cls._cfg_file_name = args.cfg
        logging.debug("Configuration file {0}.".format(cls._cfg_file_name))
        logging.debug("Loading configuration files.")
        result = cls._load_configuration_files()
        if result is False:
            logging.debug("Error while loading configuration files.")
            return -E_CONFIG_FILES
        logging.debug("Checking if the image is supported.")
        result = cls._image_is_supported()
        if result is False:
            logging.debug("Image is not supported.")
        else:
            logging.debug("Image is supported.")
        if args.testable is True:
            logging.debug("Only testability required, execution terminated.")
            if result is True:
                return 0
            else:
                return -E_UNTESTABLE
        logging.debug("Validating SW Image.")
        result = cls._validate()
        if result is True:
            logging.info("Validation Succesful.")
        else:
            logging.critical("Validation Failed.")
# pylint: enable=protected-access
        if cls._topology_class is not None and \
                cls._topology_class.reserved_device is not None:
            cls._topology_class.reserved_device.detach()
        if result is True:
            check = cls.check_test_results()
            print check
            if check:
                return 0
            else:
                return 1
        else:
            return -E_TEST_FAILED
# pylint: enable=too-few-public-methods

