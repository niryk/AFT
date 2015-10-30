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

import logging

import aft.devices.edisondevice
import aft.devices.pcdevice
import aft.cutters.clewarecutter
import aft.cutters.usbrelay

_device_classes = {
    "edison" : aft.devices.edisondevice.EdisonDevice,
    "pc" : aft.devices.pcdevice.PCDevice
}
_cutter_classes = {
    "clewarecutter" : aft.cutters.clewarecutter.ClewareCutter,
    "usbrelay" : aft.cutters.usbrelay.Usbrelay
}


def build_cutter(config):
	cutter_class = _cutter_classes[config["cutter_type"].lower()]
	return cutter_class(config)

def build_device(config, cutter):
	device_class = _device_classes[config["platform"].lower()]
	return device_class(config, cutter)