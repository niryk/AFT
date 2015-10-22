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
Catalog of recognised devices.
"""

import re
import sys
import logging
import ConfigParser

VERSION = "0.1.0"

class DevicesCatalog(list):
    """
    Loads and searches a catalog of devices.
    """
    def load(self, file_name):
        """
        Loads the catalog from disk.
        """
        del self[:]
        config = ConfigParser.SafeConfigParser()
        try:
            config.read(file_name)
            for section in config.sections():
                item = dict(config.items(section))
                item["device_model"] = section
                self.append(item)
        except ConfigParser.ParsingError as error:
            logging.critical("Error while loading catalog file {0}\n {1}"
                             .format(file_name, error))
            return False
        return self[:]

    def _search(self, key, value):
        """
        Returns the first matching catalog entry.
        """
        if "regex" in key:
            for item in self[:]:
                if re.match(item[key], "".join(value), re.DOTALL):
                    return item
        else:
            loging.critical("Searching devices catalog by unsupported key:"
                            " {0}".format(key))
        return None

    def _get_model_and_type(self, key, value):
        """
        Returns model and type of a device, based on a descriptor.
        """
        result = self._search(key, value)
        if result is None:
            return None, None
        return (result["device_model"], result["device_type"])

    def get_model_and_type_by_device(self, device_signature):
        """
        Returns model and type based on info extracted from the device.
        """
        return self._get_model_and_type("device_regex", device_signature)

    def get_model_and_type_by_file_name(self, file_name):
        """
        Returns model and type based on info extracted from the device.
        """
        return self._get_model_and_type("file_name_regex", file_name)
