# Copyright (c) 2013-15 Intel, Inc.
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

"""
Convenience functions for (unix) command execution
"""

import subprocess32

def local_execute(command, timeout = 60, ignore_return_codes = None):
    """
    Execute a command on local machine. Returns combined stdout and stderr if
    return code is 0 or included in the list 'ignore_return_codes'. Otherwise
    raises a subprocess32 error.
    """
    process = subprocess32.Popen(command, universal_newlines=True,
                                 stdout = subprocess32.PIPE,
                                 stderr = subprocess32.STDOUT)
    return_code = process.wait(timeout)
    output = process.communicate()

    if ignore_return_codes == None:
        ignore_return_codes = []
    if return_code in ignore_return_codes or return_code == 0:
        return output[0]
    else:
        raise subprocess32.CalledProcessError(returncode = return_code,
                                              cmd = command, output = output)
