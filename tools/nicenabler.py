import subprocess32
import os
import netifaces
import time
import argparse

def _get_nth_parent_dir(path, parent):
    if parent == 0:
        return path
    return _get_nth_parent_dir(os.path.dirname(path), parent - 1)

_NIC_FILESYSTEM_LOCATION = "/sys/class/net"
def find_nic_with_usb_path(usb_path):
    interfaces = netifaces.interfaces()
    for interface in interfaces:
        nic_path = os.path.realpath(os.path.join(_NIC_FILESYSTEM_LOCATION, interface))
        nic_usb_path = _get_nth_parent_dir(nic_path, 3)

        if os.path.basename(nic_usb_path) == usb_path:
            return interface
    return None

def wait_and_enable_nic(usb_path, ip):
    while (True):
        nic = find_nic_with_usb_path(usb_path)
        if not nic:
            time.sleep(1)
            continue
        subprocess32.check_call(["ifconfig", nic, ip])
        return


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=str, help="USB-tree path of the NIC")
    parser.add_argument("ip", type=str, help="IP-address/subnet to be assigned to the NIC <*.*.*.*/x>")
    args = parser.parse_args()

    while (True):
        nic = find_nic_with_usb_path(args.path)
        if not nic:
            wait_and_enable_nic(args.path, args.ip)
        time.sleep(1)

if __name__ == '__main__':
    main()