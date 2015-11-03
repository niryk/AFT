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
Base class for Cutter devices.
"""

import abc

class Cutter(object):
    """
    Common abstract base class for all the makes of cutters.
    """
    DEFAULT_TIMEOUT = 5
    __metaclass__ = abc.ABCMeta

    @abc.abstractmethod
    def connect(self):
        """
        Method connecting a channel
        """

    @abc.abstractmethod
    def disconnect(self):
        """
        Method disconnecting a channel
        """
