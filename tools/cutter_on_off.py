"""
Script to turn on and off a USB-powercutter
"""

import serial
import sys
import time

def show_help():
    """
    Print help
    """
    print sys.argv[0] + " port [0|1]"
    sys.exit(1)
if len(sys.argv) < 3 :
    show_help()

PORT = sys.argv[1]
ACTION = sys.argv[2]


SER = serial.Serial(PORT, 9600)
# disconnect
if str(ACTION) == '0' :
    SER.write('\xFE\x05\x00\x00\x00\x00\xD9\xC5')
# connect
elif str(ACTION) == '1' :
    SER.write('\xFE\x05\x00\x00\xFF\x00\x98\x35')
    
else:
    show_help()

time.sleep(1)
SER.close()

