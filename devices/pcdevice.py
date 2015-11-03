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

from aft.device import Device
import aft.tools.ssh as ssh

from pem.main import main as pem_main

VERSION = "0.1.0"

# pylint: disable=too-many-instance-attributes


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
    _SUPER_ROOT_MOUNT_POINT = "/mnt/super_target_root/"

    def __init__(self, parameters, channel):
        super(PCDevice, self).__init__(device_descriptor=parameters,
                                       channel=channel)
        self._leases_file_name = parameters["leases_file_name"]
        self._root_partition = parameters["root_partition"]
        self._service_mode_name = parameters["service_mode"]
        self._test_mode_name = parameters["test_mode"]

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

        self.dev_ip = None
        self._uses_hddimg = None

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
        self._flash_image(nfs_file_name=file_on_nfs)
        self._install_tester_public_key()
        self._enter_mode(self._test_mode)

    def get_ip(self):
        """
        Set to ip attribute and return an IP that is tested to be responsive.
        """
        leases = open(self._leases_file_name).readlines()
        filtered_leases = [line for line in leases if self.dev_id in line]
        # dnsmasq.leases contains rows with "<mac> <ip> <hostname> <domain>"
        ip_addresses = [line.split()[2] for line in filtered_leases]

        for ip_address in ip_addresses:
            result = ssh.test_ssh_connectivity(ip_address)
            if result == True:
                self.dev_ip = ip_address
                return self.dev_ip

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
        logging.info("Trying to enter " +
                     mode["name"] + " mode up to " + str(attempts) + " times.")
        for _ in range(attempts):
            self._power_cycle()

            logging.info(
                "Executing PEM with keyboard sequence " + mode["sequence"])
            pem_main(["pem", "--interface", self.pem_interface,
                      "--port", self.pem_port,
                      "--playback", mode["sequence"]])

            ip_address = self._wait_for_responsive_ip()

            if ip_address:
                if self._verify_mode(ip_address, mode["name"]):
                    return
            else:
                logging.warning("Failed entering " + mode["name"] + " mode.")

        logging.critical("Unable to get device " +
                         self.dev_id + " in mode " + mode["name"])
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

# pylint: disable=no-self-use
    def _verify_mode(self, dev_ip, mode):
        """
        Check if the device with given ip is responsive to ssh
        and in the specified mode.
        """
        sshout = ssh.remote_execute(dev_ip, ["cat", "/proc/version"])
        return mode in sshout
# pylint: enable=no-self-use

    def _flash_image(self, nfs_file_name):
        """
        Writes image into the internal storage of the device.
        """
        logging.info("Mounting the nfs containing the image to flash.")
        ssh.remote_execute(self.dev_ip, ["mount", self._IMG_NFS_MOUNT_POINT],
                           ignore_return_codes=[32])

        logging.info("Writing " + str(nfs_file_name) + "to internal storage.")
        ssh.remote_execute(self.dev_ip, ["bmaptool", "copy", "--nobmap",
                                         nfs_file_name, self._target_device],
                           timeout=self._SSH_IMAGE_WRITING_TIMEOUT)

        logging.info("Partprobing.")
        ssh.remote_execute(self.dev_ip, ["partprobe"])

    def _mount_single_layer(self):
        """
        Mount a hdddirect partition
        """
        logging.info("Mount one layer.")
        ssh.remote_execute(self.dev_ip, ["mount", self._root_partition,
                                         self._ROOT_PARTITION_MOUNT_POINT])

    def _mount_two_layers(self):
        """
        Mount a hddimg which has 'rootfs' partition
        """
        logging.info("Mounts two layers.")
        ssh.remote_execute(self.dev_ip, ["modprobe", "vfat"])

        # mount the first layer of .hddimg
        ssh.remote_execute(self.dev_ip, ["mount", self._target_device,
                                         self._SUPER_ROOT_MOUNT_POINT])
        ssh.remote_execute(self.dev_ip, ["mount", self._SUPER_ROOT_MOUNT_POINT +
                                         "rootfs",
                                         self._ROOT_PARTITION_MOUNT_POINT])

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
        root_user_home = ssh.remote_execute(self.dev_ip,
                                            ["cat", os.path.join(self._ROOT_PARTITION_MOUNT_POINT,
                                                                 "etc/passwd"),
                                             "|", "grep", "-e", '"^root"', "|",
                                             "sed", "-e", '"s/root:.*:root://"', "|",
                                             "sed", "-e", '"s/:.*//"']).rstrip().lstrip("/")

        # Ignore return value: directory might exist
        logging.info("Writing ssh-key to device.")
        ssh.remote_execute(self.dev_ip, ["mkdir", os.path.join(self._ROOT_PARTITION_MOUNT_POINT,
                                                               root_user_home, ".ssh")],
                           ignore_return_codes=[1])
        ssh.remote_execute(self.dev_ip, ["chmod", "700",
                                         os.path.join(self._ROOT_PARTITION_MOUNT_POINT,
                                                      root_user_home, ".ssh")])
        ssh.remote_execute(self.dev_ip, ["cat", "/root/.ssh/authorized_keys", ">>",
                                         os.path.join(self._ROOT_PARTITION_MOUNT_POINT,
                                                      root_user_home, ".ssh/authorized_keys")])
        ssh.remote_execute(self.dev_ip, ["chmod", "600",
                                         os.path.join(self._ROOT_PARTITION_MOUNT_POINT,
                                                      root_user_home, ".ssh/authorized_keys")])

        if not self._uses_hddimg:
            logging.info("Adding IMA attribute to the ssh-key")
            ssh.remote_execute(self.dev_ip, ["setfattr", "-n", "security.ima", "-v",
                                             "0x01`sha1sum " +
                                             os.path.join(self._ROOT_PARTITION_MOUNT_POINT,
                                                          root_user_home, ".ssh/authorized_keys") +
                                             " | cut '-d ' -f1`",
                                             os.path.join(self._ROOT_PARTITION_MOUNT_POINT,
                                                          root_user_home, ".ssh/authorized_keys")])
        logging.info("Flushing.")
        ssh.remote_execute(self.dev_ip, ["sync"])

        logging.info("Unmounting.")
        ssh.remote_execute(
            self.dev_ip, ["umount", self._ROOT_PARTITION_MOUNT_POINT])

    def execute(self, command, timeout, user="root", verbose=False):
        """
        Runs a command on the device and returns log and errorlevel.
        """
        return ssh.remote_execute(self.get_ip(), command, timeout=timeout, user=user)

    def push(self, source, destination, user="root"):
        """
        Deploys a file from the local filesystem to the device (remote).
        """
        ssh.push(self.get_ip(), source=source,
                 destination=destination, user=user)

# pylint: enable=too-many-instance-attributes
