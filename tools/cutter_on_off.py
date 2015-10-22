import serial
import sys
import time

def show_help():
    print "%s port [0|1]" % (sys.argv[0])
    sys.exit(1)
if len(sys.argv) < 3 :
    show_help()

port = sys.argv[1]
action = sys.argv[2]


ser=serial.Serial(port, 9600)
# disconnect
if str(action) == '0' :
    ser.write('\xFE\x05\x00\x00\x00\x00\xD9\xC5')
# connect
elif str(action) == '1' :
    ser.write('\xFE\x05\x00\x00\xFF\x00\x98\x35')
    
else:
    show_help()

time.sleep(1)
ser.close()

