# Copyright (c) 2015 Intel, Inc.
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

import fnmatch
import os
import subprocess32

accepted_devices = [("0b00", "3070"), ("10c4", "ea60")]

def vidpid_filter(device):
    try:
        device_info = subprocess32.check_output(["udevadm", "info", device])
        device_lines = device_info.split("\n")
        vid_line = filter(lambda line : "ID_VENDOR_ID" in line, device_lines)[0]
        pid_line = filter(lambda line : "ID_MODEL_ID" in line, device_lines)[0]
        device_vid = vid_line.split("=")[-1]
        device_pid = pid_line.split("=")[-1]

        if (device_vid, device_pid) in accepted_devices:
            return True
        return False
    except subprocess32.CalledProcessError as e:
        return False

def main():
    devices = os.listdir("/dev")
    add_dev = lambda dev : "/dev/" + dev
    devices_full_paths = map(add_dev, devices)
    tty_devices = filter(lambda dev : fnmatch.fnmatch(dev, "/dev/ttyUSB*"), devices_full_paths)
    cutter_devices = filter(vidpid_filter, tty_devices)
    for device in enumerate(cutter_devices, start=1):
        print str(1) + " " + str(device[1])
    return 0


if __name__ == '__main__':
    main()
