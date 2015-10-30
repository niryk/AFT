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

"""
Class representing a DUT which can be flashed from the testing harness and
can get an IP-address.
"""

import os
import sys
import logging
import subprocess32
import distutils.dir_util
import time
import netifaces
import shutil
import random

from aft.device import Device
from aft.tools.ssh import Ssh
from aft.tools.scp import Scp

VERSION = "0.1.0"

def _make_directory(directory):
    try:
        os.makedirs(directory)
    except OSError:
        if not os.path.isdir(directory):
            raise

def _get_nth_parent_dir(path, parent):
    if parent == 0:
        return path
    return _get_nth_parent_dir(os.path.dirname(path), parent - 1)

def _log_subprocess32_error(e):
    logging.critical(str(e.cmd) + "failed with error code: " + str(e.returncode) + " and output: " + str(e.output))
    logging.critical("Aborting")
    sys.exit(1)

class EdisonDevice(Device):
    _LOCAL_MOUNT_DIRECTORY = "edison_root_mount"
    _EDISON_DEV_ID = "8087:0a99"
    _DUT_USB_SERVICE_FILE_NAME = "usb-network.service"
    _DUT_USB_SERVICE_LOCATION = "etc/systemd/system"
    _DUT_USB_SERVICE_CONFIGURATION_FILE_NAME = "usb-network"
    _DUT_USB_SERVICE_CONFIGURATION_DIRECTORY = "etc/conf.d"
    _DUT_CONNMAN_SERVICE_FILE = "lib/systemd/system/connman.service"
    _MODULE_DATA_PATH = os.path.join(os.path.dirname(__file__), 'data')
    _FLASHER_OUTPUT_LOG="flash.log"

    @classmethod
    def init_class(cls, init_data):
        try:
            logging.debug("EdisonDevice class init_data: {0}"
                          .format(init_data))
            return True
        except KeyError as error:
            logging.critical("Error initializing Edison Device Class {0}."
                             .format(error))
            return False

    def __init__(self, parameters, channel):
        super(EdisonDevice, self).__init__(device_descriptor=
                                           parameters,
                                           channel=channel)
        Ssh.init()
        Scp.init()

        self._configuration = parameters

        self._cutter_dev_path = "/dev/ttyUSB" + self._configuration["channel"]
        self._usb_path = self._configuration["edison_usb_port"]
        subnet_parts =  self._configuration["network_subnet"].split(".") # always *.*.*.*/30
        ip_range = ".".join(subnet_parts[0:3])
        self._gateway_ip = ".".join([ip_range, str(int(subnet_parts[3]) + 0)])
        self._host_ip = ".".join([ip_range, str(int(subnet_parts[3]) + 1)])
        self._dut_ip = ".".join([ip_range, str(int(subnet_parts[3]) + 2)])
        self._broadcast_ip = ".".join([ip_range, str(int(subnet_parts[3]) + 3)])
        self._root_extension = "ext4"

    def write_image(self, file_name):
        file_no_extension = os.path.splitext(file_name)[0]
        self._mount_local(file_no_extension)
        self._add_usb_networking()
        self._add_ssh_key()
        self._unmount_local()
        
        #self._recovery_flash() # Disabled for now. Concurrency issue. Should lock the xfstk util.

        self._flashing_attempts = 0;
        logging.info("Executing flashing sequence.")
        return self._flash_image()

    def _mount_local(self, file_name):
        logging.info("Mounting the root partition for ssh-key and USB-networking service injection.")
        try:
            _make_directory(self._LOCAL_MOUNT_DIRECTORY)
            root_file_system_file = file_name + "." + self._root_extension
            subprocess32.check_call(["mount", root_file_system_file, self._LOCAL_MOUNT_DIRECTORY])
        except subprocess32.CalledProcessError as e:
            logging.debug("Failed to mount. Is AFT run as root?")
            _log_subprocess32_error(e)

    def _add_usb_networking(self):
        logging.info("Injecting USB-networking service.")
        source_file = os.path.join(self._MODULE_DATA_PATH, 
                                   self._DUT_USB_SERVICE_FILE_NAME)
        target_file = os.path.join(os.curdir, 
                                   self._LOCAL_MOUNT_DIRECTORY,
                                   self._DUT_USB_SERVICE_LOCATION,
                                   self._DUT_USB_SERVICE_FILE_NAME)
        shutil.copy(source_file, target_file)

        # Copy UID and GID
        source_stat = os.stat(source_file)
        os.chown(target_file, source_stat.st_uid, source_stat.st_gid)

        # Set symlink to start the service at the end of boot
        try:
            os.symlink(os.path.join(os.sep,
                                    self._DUT_USB_SERVICE_LOCATION,
                                    self._DUT_USB_SERVICE_FILE_NAME),
                       os.path.join(os.curdir,
                                    self._LOCAL_MOUNT_DIRECTORY,
                                    self._DUT_USB_SERVICE_LOCATION,
                                    "multi-user.target.wants",
                                    self._DUT_USB_SERVICE_FILE_NAME))
        except OSError as e:
            if e.errno == 17:
                logging.critical("The image file was not replaced. USB-networking service already exists.")
                print "The image file was not replaced! The symlink for usb-networking service already exists."
                #print "Aborting."
                #sys.exit(1)
                pass
            else:
                raise e

        # Create the service configuration file
        config_directory = os.path.join(os.curdir,
                                        self._LOCAL_MOUNT_DIRECTORY,
                                        self._DUT_USB_SERVICE_CONFIGURATION_DIRECTORY)
        _make_directory(config_directory)
        config_file = os.path.join(config_directory,
                                   self._DUT_USB_SERVICE_CONFIGURATION_FILE_NAME)

        # Service configuration options        
        config_stream = open(config_file, 'w')
        config_options = ["Interface=usb0",
                          "Address=" + self._dut_ip,
                          "MaskSize=30",
                          "Broadcast=" + self._broadcast_ip,
                          "Gateway=" + self._gateway_ip]
        for line in config_options:
            config_stream.write(line + "\n")
        config_stream.close()

        # Ignore usb0 in connman
        original_connman = os.path.join(os.curdir,
                                  self._LOCAL_MOUNT_DIRECTORY,
                                  self._DUT_CONNMAN_SERVICE_FILE)
        output_file = os.path.join(os.curdir,
                                   self._LOCAL_MOUNT_DIRECTORY,
                                   self._DUT_CONNMAN_SERVICE_FILE + "_temp")
        connman_in = open(original_connman, "r")
        connman_out = open(output_file, "w")
        for line in connman_in:
            if "ExecStart=/usr/sbin/connmand" in line:
                line = line[0:-1] + " -I usb0 \n"
            connman_out.write(line)
        connman_in.close()
        connman_out.close()
        shutil.copy(output_file, original_connman)
        os.remove(output_file)

    _HARNESS_AUTHORIZED_KEYS_FILE_NAME = "authorized_keys"
    def _add_ssh_key(self):
        logging.info("Injecting ssh-key.")
        source_file = os.path.join(self._MODULE_DATA_PATH,
                                   self._HARNESS_AUTHORIZED_KEYS_FILE_NAME)
        ssh_directory = os.path.join(os.curdir,
                                     self._LOCAL_MOUNT_DIRECTORY,
                                     "home", "root", ".ssh")
        authorized_keys_file = os.path.join(os.curdir, 
                                            ssh_directory,
                                            "authorized_keys")
        _make_directory(ssh_directory)
        shutil.copy(source_file, authorized_keys_file)
        os.chown(ssh_directory, 0, 0)
        os.chown(authorized_keys_file, 0, 0)
        # Note: incompatibility with Python 3 in chmod octal numbers
        os.chmod(ssh_directory, 0700)
        os.chmod(authorized_keys_file, 0600)

    def _unmount_local(self):
        logging.info("Flushing and unmounting the root filesystem.")
        try:
            subprocess32.check_call(["sync"])
            subprocess32.check_call(["umount", os.path.join(os.curdir, 
                                                    self._LOCAL_MOUNT_DIRECTORY)])
        except subprocess32.CalledProcessError as e:
            _log_subprocess32_error(e)

    def _reboot_device(self):
        self.channel.disconnect() #.call(["cutter_on_off", self._cutter_dev_path, "0"])
        time.sleep(1)
        self.channel.connect() #.call(["cutter_on_off", self._cutter_dev_path, "1"])

    def _recovery_flash(self):
        logging.info("Recovery flashing.")
        try:
            # This can cause race condition if multiple devices are booted at the same time!
            attempts = 0
            xfstk_parameters = ["xfstk-dldr-solo",
                                    "--gpflags", "0x80000007",
                                    "--osimage", "u-boot-edison.img",
                                    "--fwdnx", "edison_dnx_fwr.bin",
                                    "--fwimage", "edison_ifwi-dbg-00.bin",
                                    "--osdnx", "edison_dnx_osr.bin"]
            self._reboot_device()
            while (subprocess32.call(xfstk_parameters) and attempts < 10):
                logging.info("Rebooting and trying recovery flashing again. " + str(attempts))
                self._reboot_device()
                time.sleep(random.randint(10, 30))
                attempts += 1

        except subprocess32.CalledProcessError as e:
            _log_subprocess32_error(e)
        except OSError as e:
            logging.critical("Failed recovery flashing, errno = " + str(e.errno) + ". Is the xFSTK tool installed?")
            sys.exit(1)

    def _wait_for_device(self):
        start = time.time()
        timeout = 15
        while time.time() - start < 15:
            output = subprocess32.check_output(["dfu-util", "-l", "-d", self._EDISON_DEV_ID])
            output_lines = output.split("\n")
            fitting_lines = [line for line in output_lines if 'path="' + self._usb_path + '"' in line]
            if fitting_lines:
                return
            else:
                continue
        raise IOError("Could not find the device in DFU-mode in 15 seconds.")

    def _dfu_call(self, alt, source, extras = [], attempts = 4, timeout = 600):
        flashing_log_file = open(self._FLASHER_OUTPUT_LOG, "a")
        attempt = 0
        while attempt < attempts:
            self._wait_for_device()
            execution = subprocess32.Popen(["dfu-util", "-v", "--path", self._usb_path, 
                                          "--alt", alt, "-D", source] + extras, 
                                          stdout=flashing_log_file,
                                          stderr=flashing_log_file)
            start = time.time()
            while time.time() - start < timeout:
                status = execution.poll()
                if (status == None):
                    continue
                else:
                    flashing_log_file.close()
                    return
            
            try:
                execution.kill()
            except OSError as e: 
                if e.errno == 3:
                    pass
                else:
                    raise
            attempt += 1
            
            logging.warning("Flashing failed on alt " + alt + " for file " + source + " on USB-path " + self._usb_path + ". Rebooting and attempting again for " + str(attempt) + "/" + str(attempts) + " time.")
            self._reboot_device()
        flashing_log_file.close()
        raise IOError("Flashing failed 4 times. Raising error (aborting).")


    IFWI_DFU_FILE = "edison_ifwi-dbg"
    def _flash_image(self):
        self._reboot_device()
        logging.info("Flashing IFWI.")
        for i in range(0, 7):
            si = str(i)
            self._dfu_call("ifwi0" + si, self.IFWI_DFU_FILE + "-0"  + si + "-dfu.bin")
            self._dfu_call("ifwib0" + si, self.IFWI_DFU_FILE + "-0" + si + "-dfu.bin")

        logging.info("Flashing u-boot")
        self._dfu_call("u-boot0", "u-boot-edison.bin")
        self._dfu_call("u-boot-env0", "u-boot-envs/edison-blankcdc.bin")
        self._dfu_call("u-boot-env1", "u-boot-envs/edison-blankcdc.bin", ["-R"])
        self._wait_for_device()

        logging.info("Flashing boot partition.")
        self._dfu_call("boot", "iot-os-image-edison." + self._configuration["boot_extension"])
        logging.info("Flashing update partition.")
        self._dfu_call("update", "iot-os-image-edison." + self._configuration["recovery_extension"])
        logging.info("Flashing root partition.")
        self._dfu_call("rootfs", "iot-os-image-edison." + self._configuration["root_extension"], ["-R"])
        logging.info("Flashing complete.")
        return True

    def test(self, test_case):
        self.open_interface()
        enabler = subprocess32.Popen(["python", os.path.join(os.path.dirname(__file__), os.path.pardir, "tools", "nicenabler.py"), self._usb_path, self._host_ip + "/30"])
        self._wait_until_ssh_visible()
        tester_result = test_case.run(self)
        enabler.kill()
        return tester_result

    def execute(self, command, timeout, user="root", verbose=False):
        pass

    def push(self, local_file, remote_file, user="root"):
        pass

    def is_in_test_mode(self):
        return True

    def is_in_service_mode(self):
        return True

    def open_interface(self):
        interface = self._get_usb_nic()
        ip_subnet = self._host_ip + "/30"
        logging.info("Opening the host network interface for testing.")
        subprocess32.check_call(["ifconfig", interface, "up"])
        subprocess32.check_call(["ifconfig", interface, ip_subnet])

    def _wait_until_ssh_visible(self, timeout = 60):
        start = time.time()
        while (time.time() - start < timeout):
            retval = Ssh.execute(dev_ip=self._dut_ip, 
                                 command=("ps", ), 
                                 timeout=10, )
            if retval is not None and retval.returncode == 0:
                return
        logging.critical("Failed to establish ssh-connection in " + str(timeout) + " seconds after enabling the network interface.")
        raise IOError("Failed to establish ssh-connection in " + str(timeout) + " seconds after enabling the network interface.")


    def get_ip(self):
        return self._dut_ip

    _NIC_FILESYSTEM_LOCATION = "/sys/class/net"
    def _get_usb_nic(self, timeout = 120):
        logging.info("Searching for the host network interface from usb path " + self._usb_path)
        start = time.time()
        while time.time() - start < timeout:

            interfaces = netifaces.interfaces()
            for interface in interfaces:
                try:
                    # Test if the interface is the correct USB-ethernet NIC
                    nic_path = os.path.realpath(os.path.join(self._NIC_FILESYSTEM_LOCATION, interface))
                    usb_path = _get_nth_parent_dir(nic_path, 3)
                    
                    if os.path.basename(usb_path) == self._usb_path:
                        return interface
                except IOError as e:
                    print "IOError: " + str(e.errno) + " " + e.message
                    print "Error likely caused by jittering network interface. Ignoring."
                    logging.warning("An IOError occured when testing network interfaces. IOERROR: " + str(e.errno) + " " + e.message)
                    pass
            time.sleep(1)

        raise ValueError("Could not find a network interface from USB-path " + self._usb_path + " in 120 seconds.")
