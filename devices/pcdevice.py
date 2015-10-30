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
Class representing a PC-like Device with an IP.
"""

import os
import time
import logging
import sys

from aft.device import Device
from aft.tools.ssh import Ssh
from aft.tools.scp import Scp

from pem.main import main as pem_main

VERSION = "0.1.0"


class PCDevice(Device):
    """
    Class representing a PC-like device.
    """
    _BOOT_TIMEOUT = 240
    _POLLING_INTERVAL = 10
    _POWER_CYCLE_DELAY = 10
    _SSH_SHORT_GENERIC_TIMEOUT = 10
    _SSH_IMAGE_WRITING_TIMEOUT = 720
    _IMG_NFS_MOUNT_POINT = "/mnt/img_data_nfs"
    _ROOT_PARTITION_MOUNT_POINT = "/mnt/target_root/"
    _SUPER_ROOT_PARTITION_MOUNT_POINT = "/mnt/super_target_root/"

    @classmethod
    def init_class(cls, init_data):
        """
        Initializer for class variables and parent class.
        """
        try:
            return True
        except KeyError as error:
            logging.critical("Error initializing PC Device Class {0}."
                             .format(error))
            return False

    def __init__(self, parameters, channel):
        super(PCDevice, self).__init__(device_descriptor=
                                       parameters,
                                       channel=channel)
        self._leases_file_name = parameters["leases_file_name"]
        self._root_partition = parameters["root_partition"]
        self._service_mode_name = parameters["service_mode"]
        self._test_mode_name = parameters["test_mode"]
        Ssh.init()
        Scp.init()

        self.pem_interface = parameters["pem_interface"]
        self.pem_port = parameters["pem_port"]
        self._test_mode = {
            "name": self._test_mode_name,
            "sequence": parameters["test_mode_keystrokes"]}
        self._service_mode = {
            "name": self._service_mode_name,
            "sequence": parameters["service_mode_keystrokes"]}
        self._target_device = \
            parameters["target_device"]

    def write_image(self, file_name):
        """
        Method for writing an image to a device.
        """
        # NOTE: it is expected that the image is located somewhere
        # underneath /home/tester, therefore symlinks outside of it
        # will not work
        # The /home/tester path is exported as nfs and mounted remotely as
        # _IMG_NFS_MOUNT_POINT

        # Bubblegum fix to support both .hddimg and .hdddirect at the same time 
        if os.path.splitext(file_name)[-1] == ".hddimg":
            self._uses_hddimg = True
        else:
            self._uses_hddimg = False
        
        self._enter_mode(self._service_mode)

        file_on_nfs = os.path.abspath(file_name).replace("home/tester",
                                             self._IMG_NFS_MOUNT_POINT)

        if not self._flash_image(nfs_file_name=file_on_nfs):
            logging.info("Flashing image failed")
            return False
        elif not self._install_tester_public_key():
            logging.info("Couldn't install the SSH key")
            return False

        self._enter_mode(self._test_mode)
        logging.info("Image {0} written.".format(file_name))
        return True

    def get_ip(self):
        """
        Check if the device is responsive to ssh
        """
        leases = open(self._leases_file_name).readlines()
        filtered_leases = filter(lambda line : self.dev_id in line, leases)
        # dnsmasq.leases contains rows with "<mac> <ip> <hostname> <domain>"
        ip_addresses = map(lambda line : line.split()[2], filtered_leases)
        
        for ip in ip_addresses:
            result = Ssh.execute(dev_ip=ip, command=("echo", "$?"),
                                 timeout=self._SSH_SHORT_GENERIC_TIMEOUT, )
            if (result != None) and (result.returncode == 0):
                return ip

    def _power_cycle(self):
        """
        Reboot the device.
        """
        logging.info("Rebooting the device.")
        self.detach()
        time.sleep(self._POWER_CYCLE_DELAY)
        self.attach()

    def _enter_mode(self, mode):
        """
        Tries to put the device into the specified mode.
        """
        # Sometimes booting to a mode fails.
        attempts = 8
        logging.info("Trying to enter " + mode["name"] + " mode up to " + str(attempts) + " times.")
        for _ in range(attempts):
            self._power_cycle()

            logging.info("Executing PEM with keyboard sequence " + mode["sequence"])
            pem_main(["pem", "--interface", self.pem_interface,
                      "--port", self.pem_port,
                      "--playback", mode["sequence"]])

            ip = self._wait_for_responsive_ip()

            if ip:
                if self._verify_mode(ip, mode["name"]):
                    return
            else:
                logging.warning("Failed entering " + mode["name"] + " mode.")

        logging.critical("Unable to get device {0} in mode \"{1}.\""
                         .format(self.dev_id, mode["name"]))
        raise LookupError("Could not set the device in mode " + mode["name"])

    def _wait_for_responsive_ip(self):
        """
        For a limited amount of time, try to assess if the device
        is in the mode requested.
        """
        logging.info("Waiting for the device to become responsive")
        for _ in range(self._BOOT_TIMEOUT / self._POLLING_INTERVAL):
            responsive_ip = self.get_ip()
            if not responsive_ip:
                time.sleep(self._POLLING_INTERVAL)
                continue
            logging.info("Got a respond from " + responsive_ip)
            return responsive_ip

    def _verify_mode(self, dev_ip, mode):
        """
        Check if the device with given ip is responsive to ssh
        and in the specified mode.
        """
        retval = Ssh.execute(dev_ip=dev_ip,
                             command=("cat", "/proc/version", "|",
                                      "grep", mode),
                             timeout=self._SSH_SHORT_GENERIC_TIMEOUT, )
        if retval is None or retval.returncode is not 0:
            logging.debug("Ssh failed.")
        elif mode not in retval.stdoutdata:
            logging.debug("Device not in \"{0}\" mode.".format(mode))
        else:
            logging.debug("Device in \"{0}\" mode.".format(mode))

        return retval is not None and \
               retval.returncode is 0 and \
               mode in retval.stdoutdata

    def _flash_image(self, nfs_file_name):
        """
        Writes image into the internal storage of the device.
        """
        logging.info("Mounting the nfs containing the image to flash.")
        result = self.execute(
            command=("mount", self._IMG_NFS_MOUNT_POINT),
            timeout=self._SSH_SHORT_GENERIC_TIMEOUT,
        )
        if result == None:
            logging.critical("Failed to interact with the device.")
            return False
        logging.info("Testing for availability of image {0} ."
                     .format(nfs_file_name))
        result = self.execute(
            command=("[", "-f", nfs_file_name, "]", "&&",
                     "echo", "found", "||", "echo", "missing"),
            timeout=self._SSH_SHORT_GENERIC_TIMEOUT,
            verbose=True,
        )
        logging.info(result)
        if result != None and "found" in result.stdoutdata:
            logging.info("Image found.")
        else:
            logging.critical("Image \"{0}\" not found."
                             .format(nfs_file_name))
            return False
        logging.info("Writing image {0} to internal storage."
                     .format(nfs_file_name))
        result = self.execute(command=("bmaptool", "copy", "--nobmap",
                                       nfs_file_name, self._target_device),
                              timeout=self._SSH_IMAGE_WRITING_TIMEOUT,)
        if result != None and result.returncode == 0:
            logging.info("Image written successfully.")
        else:
            logging.critical("Error while writing image to device.")
            return False
        result = self.execute(command=("partprobe", ),
				timeout=self._SSH_SHORT_GENERIC_TIMEOUT, )
        if result != None and result.returncode == 0:
            logging.info("Partprobed succesfully.")
            return True
        else:
            logging.critical("Partprobing failed.")
            return False

    def _mount_single_layer(self):
        logging.info("mount one layer")
        result = self.execute(
            command=("mount", self._root_partition,
                     self._ROOT_PARTITION_MOUNT_POINT),
                     timeout=self._SSH_SHORT_GENERIC_TIMEOUT, )
        if result is None or result.returncode != 0:
            logging.critical("Failed mounting internal storage.\n{0}"
                             .format(result))
#           return False        
    
    def _mount_two_layers(self):
        logging.info("mounts two layers")
        result = self.execute(
            command=("modprobe", "vfat"),
                     timeout=self._SSH_SHORT_GENERIC_TIMEOUT, )
        logging.info("modprobe vfat returncode: " + str(result.returncode)
                     + ".\n{0}" .format(result))
        # mount the first layer of .hddimg
        result = self.execute(
            command=("mount", self._target_device,
                     self._SUPER_ROOT_PARTITION_MOUNT_POINT),
                     timeout=self._SSH_SHORT_GENERIC_TIMEOUT, )
        if result is None or result.returncode is not 0:
            logging.critical("Failed mounting internal hddimg storage.\n{0}"
                             .format(result))
            return False
        #mount the second layer of .hddimg
        result = self.execute(
            command=("mount", self._SUPER_ROOT_PARTITION_MOUNT_POINT + 
                     self._rootfs_filename, 
                     self._ROOT_PARTITION_MOUNT_POINT),
                     timeout=self._SSH_SHORT_GENERIC_TIMEOUT, )
        if result is None or result.returncode is not 0:
            logging.critical("Failed mounting the rootfs of hddimg.\n{0}"
                             .format(result))
            return False

    def _install_tester_public_key(self):
        """
        Copy ssh public key to root user on the target device.
        """
        # update info about the partition table
        if not self._uses_hddimg:
            self._mount_single_layer()
        else:
            self._mount_two_layers()
      # Identify the home of the root user
        result = self.execute(
            command=("cat",
                     os.path.join(self._ROOT_PARTITION_MOUNT_POINT,
                                  "etc/passwd"), "|",
                     "grep", "-e", '"^root"', "|",
                     "sed", "-e" '"s/root:.*:root://"', "|",
                     "sed", "-e" '"s/:.*//"'),
            timeout=self._SSH_SHORT_GENERIC_TIMEOUT, )
        if result is None or result.returncode is not 0:
            logging.critical("Failed to identify the home of the root user.")
            return False
        else:
            root_user_home = result.stdoutdata.rstrip().strip("/")
        # Ignore return value: directory might exist
        result = self.execute(
            command=("mkdir", os.path.join(self._ROOT_PARTITION_MOUNT_POINT,
                     root_user_home, ".ssh")),
            timeout=self._SSH_SHORT_GENERIC_TIMEOUT, )
        if result is None:
            logging.critical("Failed to ssh into the device.")
        elif result.returncode is not 0:
            logging.info(".ssh directory already present for root user.")
        result = self.execute(
            command=("chmod", "700",
                     os.path.join(self._ROOT_PARTITION_MOUNT_POINT,
                     root_user_home, ".ssh")),
            timeout=self._SSH_SHORT_GENERIC_TIMEOUT, )
        if result is None:
            logging.critical("Failed to ssh into the device.")
        # replicate the public key used for logging in as root
        result = self.execute(
            command=("cat", "/root/.ssh/authorized_keys", ">>",
                     os.path.join(self._ROOT_PARTITION_MOUNT_POINT,
                     root_user_home, ".ssh/authorized_keys")),
            timeout=self._SSH_SHORT_GENERIC_TIMEOUT, )
        if result is None or result.returncode is not 0:
            logging.critical("Failed writing the public key to the device.")
            return False
        result = self.execute(
            command=("chmod", "600",
                     os.path.join(self._ROOT_PARTITION_MOUNT_POINT,
                                  root_user_home, ".ssh/authorized_keys")),
            timeout=self._SSH_SHORT_GENERIC_TIMEOUT, )
        if result is None:
            logging.critical("Failed to ssh into the device.")
            return False
        if not self._uses_hddimg: #add the security.ima extra attr
            result = self.execute(
                command=("setfattr", "-n", "security.ima", "-v", 
                        "0x01`sha1sum ", 
                        os.path.join(self._ROOT_PARTITION_MOUNT_POINT,
                        root_user_home, ".ssh/authorized_keys"), "|", "cut",
                        "'-d '", "-f1`", 
                        os.path.join(self._ROOT_PARTITION_MOUNT_POINT,
                        root_user_home, ".ssh/authorized_keys")),
                timeout=self._SSH_SHORT_GENERIC_TIMEOUT, )
        result = self.execute(
            command=("sync",), timeout=self._SSH_SHORT_GENERIC_TIMEOUT, )
        if result is None or result.returncode is not 0:
            logging.critical("Failed flushing internal storage.")
            return False
        result = self.execute(
            command=("umount", self._ROOT_PARTITION_MOUNT_POINT),
            timeout=self._SSH_SHORT_GENERIC_TIMEOUT, )
        if result is None or result.returncode is not 0:
            logging.critical("Failed unmounting internal storage.")
            return False
        logging.info("Public key written successfully to device.")
        return True

    def execute(self, command, timeout, environment=(),
                user="root", verbose=False):
        """
        Runs a command on the device and returns log and errorlevel.
        """
        return Ssh.execute(dev_ip=self.get_ip(), timeout=timeout,
                           user=user, environment=environment, command=command,
                           verbose=verbose)

    def push(self, source, destination, user="root"):
        """
        Deploys a file from the local filesystem to the device (remote).
        """
        return Scp.push(self.get_ip(), source=source,
                        destination=destination, user=user)
