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
Topology of devices and cutters connected to the host PC.
"""

import os
import abc
import sys
import time
import errno
import fcntl
import atexit
import logging
import ConfigParser
from aft.devicescatalog import DevicesCatalog

VERSION = "0.1.0"


class DevicesTopology(object):
    """
    Class handling the layout of devices and cutters.
    """
    __metaclass__ = abc.ABCMeta
    _LOCK_ROOT = os.getenv("AFT_LOCKROOT", "/var/lock/")
    _device_class = None
    _cutter_class = None
    _model = None
    _dev_type = None
    _devices = None
    _lockfile = None
    reserved_device = None
    _topology_file_name = None
    _devices_catalog = None

    @classmethod
    def init(cls, topology_file_name, catalog_file_name,
             device_class, cutter_class):
        """
        Initializer for class variables.
        """
        logging.debug("Initializing Topology:\n" +
                      "\tdevice class: {0}\n".format(device_class) +
                      "\tcutter class: {0}\n".format(cutter_class) +
                      "\ttopology file: {0}\n".format(topology_file_name))
        cls._device_class = device_class
        cls._cutter_class = cutter_class
        cls._topology_file_name = topology_file_name
        cls._devices_catalog = DevicesCatalog()
        return cls._devices_catalog.load(catalog_file_name) and \
            cls._cutter_class.init()

    @classmethod
    def load(cls):
        """
        Load configuration file with layout of DUTs and cutters.
        """
        device_class_names = {"Edison" : "EdisonDevice",
                              "GalileoV2" : "PCDevice",
                              "Gigabyte" : "PCDevice"}

        config = ConfigParser.ConfigParser()
        cls._devices = []
        try:
            logging.debug("Loading topology file: {0}".
                          format(cls._topology_file_name))
            config.read(cls._topology_file_name)
            logging.debug("Topology file loaded.")
            for section in config.sections():
                device_descriptor = dict(config.items(section))
                if device_class_names[device_descriptor["model"]] != cls._device_class.__name__:
                    continue
                device_descriptor["name"] = section
                for item in cls._devices_catalog:
                    if item["device_model"] == device_descriptor["model"]:
                        device_descriptor["catalog_entry"] = item
                        break
                logging.debug("Processing device descriptor: {0}".
                              format(device_descriptor))
                logging.debug("Acquiring cutter.")
                channel = \
                    cls._cutter_class.get_channel_by_id_and_cutter_id(
                        device_descriptor["cutter"],
                        device_descriptor["channel"])
                logging.debug("Channel acquired: {0}".format(channel))
                device_class = cls._device_class(device_descriptor=
                                                 device_descriptor,
                                                 channel=channel)
                logging.debug("Device Class created as: {0}".
                              format(device_class))
                cls._devices.append(device_class)
            logging.debug("Devices: {0}".format(cls._devices))
            return True
        except (OSError, ConfigParser.ParsingError) as error:
            logging.critical("Error while loading config file {0}\n {1}"
                             .format(cls._topology_file_name, error))
            return False

    @classmethod
    @abc.abstractmethod
    def _detect(cls, force=False):
        """
        Detects topology of connections between host and DUTs.
        """
        if cls._devices and not force:
            return False
        cls._devices = []
        return True

    @classmethod
    def _save(cls):
        """
        Store the topology in a cfg file.
        """
        config = ConfigParser.ConfigParser()
        for device in cls._devices:
            config.add_section(device.name)
            config.set(device.name, "model", device.model)
            config.set(device.name, "id", device.dev_id)
            config.set(device.name, "cutter", device.channel.cutter_id)
            config.set(device.name, "channel", device.channel.cutter_ch)
        try:
            with open(cls._topology_file_name, "w") as config_file:
                os.chmod(cls._topology_file_name, 0644)
                config.write(config_file)
        except (OSError, ConfigParser.ParsingError) as error:
            logging.critical("Error while writing config file {0}\n {1}"
                             .format(cls._topology_file_name, error))
            sys.exit(-1)

    @classmethod
    def generate(cls):
        """
        Creates the configuration file describing how devices and cutters
        are connected.
        """
        cls._detect(force=True)
        cls._save()

    @classmethod
    def identify_model_and_type(cls, file_name):
        """
        Verifies if there is any known device mode/type that is compatible
        with the candidate image.
        """
        cls._model, cls._dev_type = \
            cls._devices_catalog.get_model_and_type_by_file_name(file_name)
        return cls._model is not None and cls._dev_type is not None

    @classmethod
    def reserve(cls):
        """
        Searches and reserves a device that is compatible with the type of
        image that will be written.
        """
        present = False
        # Loop as long as there are compatible devices, but busy
        while True:
            #print cls._devices
            for device in cls._devices:
                if cls._dev_type in device.name and \
                        cls._model == device.model:
                    present = True
                    logging.info("Attempting to acquire {0} {1}"
                                 .format(cls._model, device.dev_id))
                    try:
                        old_mask = os.umask(011)
                        cls._lockfile = \
                            os.fdopen(os.open(
                                os.path.join(cls._LOCK_ROOT,
                                             "aft_" + device.dev_id),
                                os.O_WRONLY | os.O_CREAT, 0660), "w")
                        os.umask(old_mask)
                        #print cls._lockfile
                        fcntl.flock(cls._lockfile,
                                    fcntl.LOCK_EX | fcntl.LOCK_NB)
                        logging.info("Device acquired.")
                        cls.reserved_device = device
                        atexit.register(cls.release)
                        return device
                    except IOError as err:
                        if err.errno in {errno.EACCES, errno.EAGAIN}:
                            logging.info("All devices busy ... trying later.")
                        else:
                            logging.critical("Cannot obtain lock file.")
                            sys.exit(-1)
            if not present:
                cls.reserved_device = None
                return None
            logging.info("Sleeping 10s")
            time.sleep(10)

    @classmethod
    def release(cls):
        """
        Put the reserved device back to the pool. It will happen anyway when
        the process dies, but this removes the stale lockfile.
        """
        if cls.reserved_device and cls._lockfile:
            cls._lockfile.close()
            os.unlink(os.path.join(cls._LOCK_ROOT,
                                   "aft_" + cls.reserved_device.dev_id))
