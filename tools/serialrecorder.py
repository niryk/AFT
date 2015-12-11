# Copyright (c) 2013-15 Intel, Inc.
# Author Topi Kuutela <topi.kuutela@intel.com>
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
A script to record serial output from a tty-device.
"""

import serial
import argparse
import signal
import time
import re

TERMINATE_FLAG = False
def signal_handler():
    """
    Terminal signal handler
    """
    # pylint: disable=global-statement
    global TERMINATE_FLAG
    # pylint: enable=global-statement
    print "Terminating serial recorder."
    TERMINATE_FLAG = True

def main():
    """
    Initialization.
    """
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    parser = argparse.ArgumentParser()
    parser.add_argument("port", type=str, help="Serial port to read from (e.g. /dev/ttyUSB0)")
    parser.add_argument("--rate", type=int, default=115200, help="Baud rate of the serial port")
    parser.add_argument("output", type=str, help="Output file name")
    args = parser.parse_args()

    serial_stream = serial.Serial(args.port, args.rate, timeout=0.01, xonxoff=True)
    output_file = open(args.output, "w")

    print "Starting recording from " + str(args.port) + " to " + str(args.output) + "."
    record(serial_stream, output_file)

    output_file.close()

def record(serial_stream, output):
    """
    Recording loop
    """
    read_buffer = ""
    while True:
        read_buffer += serial_stream.read(4096)

        last_newline = read_buffer.rfind("\n")
        if last_newline == -1 and not TERMINATE_FLAG:
            continue

        text_batch = read_buffer[0:last_newline + 1]
        read_buffer = read_buffer[last_newline + 1:-1]

        text_batch = re.sub(r'\x1b\[([0-9,A-Z]{1,2}(;[0-9]{1,2})?(;[0-9]{3})?)?[m|K]?',
                            '', text_batch)

        time_now = time.time()
        timed_batch = text_batch.replace("\n", "\n[" + str(time_now) + "] ")
        output.write(timed_batch)
        if TERMINATE_FLAG:
            return

if __name__ == '__main__':
    main()
