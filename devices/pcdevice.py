# coding=utf-8
# Copyright (c) 2013-2016 Intel, Inc.
# Author Igor Stoppa <igor.stoppa@intel.com>
# Author Topi Kuutela <topi.kuutela@intel.com>
# Author Erkka Kääriä <erkka.kaaria@intel.com>
# Author Simo Kuusela <simo.kuusela@intel.com>
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
import json
from multiprocessing import Process, Queue

from aft.logger import Logger as logger
import aft.config as config
from aft.devices.device import Device
import aft.errors as errors
import aft.tools.ssh as ssh
import aft.devices.common as common

from pem.main import main as pem_main

VERSION = "0.1.0"

# pylint: disable=too-many-instance-attributes


class PCDevice(Device):
    """
    Class representing a PC-like device.

    Attributes:
        _RETRY_ATTEMPTS (integer):
            How many times the device attempts to enter the requested mode
            (testing/service) before givingup

        _BOOT_TIMEOUT (integer):
            The device boot timeout. Used when waiting for responsive ip address

        _POLLING_INTERVAL (integer):
            The polling interval used when waiting for responsive ip address

        _SSH_IMAGE_WRITING_TIMEOUT (integer):
            The timeout for flashing the image.

        _IMG_NFS_MOUNT_POINT (str):
            The location where the service OS mounts the nfs filesystem so that
            it can access the image file etc.

        _ROOT_PARTITION_MOUNT_POINT (str):
            The location where the service OS mounts the image root filesystem
            for SSH key injection.

        _SUPER_ROOT_MOUNT_POINT (str):
            Mount location used when having to mount two layers



    """
    _RETRY_ATTEMPTS = 4
    _BOOT_TIMEOUT = 240
    _POLLING_INTERVAL = 10
    _SSH_IMAGE_WRITING_TIMEOUT = 1440
    _IMG_NFS_MOUNT_POINT = "/mnt/img_data_nfs"
    _ROOT_PARTITION_MOUNT_POINT = "/mnt/target_root/"
    _SUPER_ROOT_MOUNT_POINT = "/mnt/super_target_root/"


    def __init__(self, parameters, channel):
        """
        Constructor

        Args:
            parameters (Dictionary): Device configuration parameters
            channel (aft.Cutter): Power cutter object
        """

        super(PCDevice, self).__init__(device_descriptor=parameters,
                                       channel=channel)


        self.retry_attempts = 4

        self._leases_file_name = parameters["leases_file_name"]
        self.default_root_patition = parameters["root_partition"]
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


        self._config_check_keystrokes = parameters["config_check_keystrokes"]

        self.dev_ip = None
        self._uses_hddimg = None

# pylint: disable=no-self-use


# pylint: enable=no-self-use

    def write_image(self, file_name):
        """
        Method for writing an image to a device.

        Args:
            file_name (str):
                The file name of the image that will be flashed on the device

        Returns:
            None
        """
        # NOTE: it is expected that the image is located somewhere
        # underneath config.NFS_FOLDER (default: /home/tester),
        # therefore symlinks outside of it will not work
        # The config.NFS_FOLDER path is exported as nfs and mounted remotely as
        # _IMG_NFS_MOUNT_POINT

        # Bubblegum fix to support both .hddimg and .hdddirect at the same time
        self._uses_hddimg = os.path.splitext(file_name)[-1] == ".hddimg"

        self._enter_mode(self._service_mode)
        file_on_nfs = os.path.abspath(file_name).replace(
            config.NFS_FOLDER,
            self._IMG_NFS_MOUNT_POINT)

        self._flash_image(nfs_file_name=file_on_nfs, filename=file_name)
        self._install_tester_public_key(file_name)

    def _run_tests(self, test_case):
        """
        Boot to test-mode and execute testplan.

        Args:
            test_case (aft.TestCase): Test case object

        Returns:
            The return value of the test_case run()-method
            (implementation class specific)
        """
        self._enter_mode(self._test_mode)
        return test_case.run(self)

    def get_ip(self):
        """
        Returns device ip address

        Returns:
            (str): The device ip address
        """
        return common.get_ip_for_pc_device(
            self.dev_id,
            self.parameters["leases_file_name"])

    def _enter_mode(self, mode):
        """
        Try to put the device into the specified mode.

        Args:
            mode (Dictionary):
                Dictionary that contains the mode specific information

        Returns:
            None

        Raises:
            aft.errors.AFTDeviceError if device fails to enter the mode or if
            PEM fails to connect

        """
        # Sometimes booting to a mode fails.

        logger.info(
            "Trying to enter " + mode["name"] + " mode up to " +
            str(self._RETRY_ATTEMPTS) + " times.")

        for _ in range(self._RETRY_ATTEMPTS):
            self._power_cycle()

            logger.info(
                "Executing PEM with keyboard sequence " + mode["sequence"])

            self._send_PEM_keystrokes(mode["sequence"])

            ip_address = self._wait_for_responsive_ip()

            if ip_address:
                if self._verify_mode(mode["name"]):
                    return
            else:
                logger.warning("Failed entering " + mode["name"] + " mode.")

        logger.critical(
            "Unable to get device " + self.dev_id + " in mode " +
            mode["name"])

        raise errors.AFTDeviceError(
            "Could not set the device in mode " + mode["name"])


    def _send_PEM_keystrokes(self, keystrokes, attempts=1, timeout=60):
        """
        Try to send keystrokes within the time limit

        Args:
            keystrokes (str): PEM keystroke file
            attempts (integer): How many attempts will be made
            timeout (integer): Timeout for a single attempt

        Returns:
            None

        Raises:
            aft.errors.AFTDeviceError if PEM connection times out

        """
        def call_pem(exceptions):
            try:
                pem_main(
                [
                    "pem",
                    "--interface", self.pem_interface,
                    "--port", self.pem_port,
                    "--playback", keystrokes
                ])
            except Exception as err:
                exceptions.put(err)

        for i in range(attempts):
            logger.info(
                "Attempt " + str(i + 1) + " of " + str(attempts) + " to send " +
                "keystrokes through PEM")

            exception_queue = Queue()
            process = Process(target=call_pem, args=(exception_queue,))
            # ensure python process is closed in case main process dies but
            # the subprocess is still waiting for timeout
            process.daemon = True

            process.start()
            process.join(timeout)

            if not exception_queue.empty():
                raise exception_queue.get()

            if process.is_alive():
                process.terminate()
            else:
                return

        raise errors.AFTDeviceError("Failed to connect to PEM")

    def _wait_for_responsive_ip(self):
        """
        For a limited amount of time, try to assess if the device
        is in the mode requested.

        Returns:
            (str or None):
                The device ip, or None if no active ip address was found
        """

        self.dev_ip = common.wait_for_responsive_ip_for_pc_device(
            self.dev_id,
            self.parameters["leases_file_name"],
            self._BOOT_TIMEOUT,
            self._POLLING_INTERVAL)

        return self.dev_ip

    def _verify_mode(self, mode):
        """
        Check if the device with given ip is responsive to ssh
        and in the specified mode.

        Args:
            mode (str): The name of the mode that the device should be in.

        Returns:
            True if device is in the desired mode, False otherwise
        """
        return common.verify_device_mode(self.dev_ip, mode)

    def _flash_image(self, nfs_file_name, filename):
        """
        Writes image into the internal storage of the device.

        Args:
            nfs_file_name (str): The image file path on the nfs
            filename (str): The image filename

        Returns:
            None
        """
        logger.info("Mounting the nfs containing the image to flash.")
        ssh.remote_execute(self.dev_ip, ["mount", self._IMG_NFS_MOUNT_POINT],
                           ignore_return_codes=[32])

        logger.info("Writing " + str(nfs_file_name) + " to internal storage.")

        bmap_args = ["bmaptool", "copy", nfs_file_name, self._target_device]
        if os.path.isfile(filename + ".bmap"):
            logger.info("Found "+ filename +".bmap. Using bmap for flashing.")

        else:
            logger.info("Didn't find " + filename +
                         ".bmap. Flashing without it.")
            bmap_args.insert(2, "--nobmap")

        ssh.remote_execute(self.dev_ip, bmap_args,
                           timeout=self._SSH_IMAGE_WRITING_TIMEOUT)

        # Flashing the same file as already on the disk causes non-blocking
        # removal and re-creation of /dev/disk/by-partuuid/ files. This sequence
        # either delays enough or actually settles it.
        logger.info("Partprobing.")
        ssh.remote_execute(self.dev_ip, ["partprobe", self._target_device])
        ssh.remote_execute(self.dev_ip, ["sync"])
        ssh.remote_execute(self.dev_ip, ["udevadm", "trigger"])
        ssh.remote_execute(self.dev_ip, ["udevadm", "settle"])
        ssh.remote_execute(self.dev_ip, ["udevadm", "control", "-S"])

    def _mount_single_layer(self, image_file_name):
        """
        Mount a hdddirect partition

        Returns:
            None
        """

        logger.info("Mount one layer.")
        ssh.remote_execute(
            self.dev_ip,
            [
                "mount",
                self.get_root_partition_path(image_file_name),
                self._ROOT_PARTITION_MOUNT_POINT])


    def get_root_partition_path(self, image_file_name):
        """
        Select either the default config value to be the root_partition
        or if the disk layout file exists, use the rootfs from it.

        Args:
            image_file_name (str): The name of the image file. Disk layout file
            name is based on this

        Returns:
            (str): path to the disk pseudo file
        """

        layout_file_name = self.get_layout_file_name(image_file_name)

        if not os.path.isfile(layout_file_name):
            logger.info("Disk layout file " + layout_file_name  +
                         " doesn't exist. Using root_partition from config.")
            return self.default_root_patition

        layout_file = open(layout_file_name, "r")
        disk_layout = json.load(layout_file)
        rootfs_partition = next(
            partition for partition in list(disk_layout.values()) \
            if isinstance(partition, dict) and \
            partition["name"] == "rootfs")
        return os.path.join(
            "/dev",
            "disk",
            "by-partuuid",
            rootfs_partition["uuid"])


    def get_layout_file_name(self, image_file_name):
        return image_file_name.split(".")[0] + "-disk-layout.json"

    def _mount_two_layers(self):
        """
        Mount a hddimg which has 'rootfs' partition

        Returns:
            None
        """
        logger.info("Mounts two layers.")
        ssh.remote_execute(self.dev_ip, ["modprobe", "vfat"])

        # mount the first layer of .hddimg
        ssh.remote_execute(self.dev_ip, ["mount", self._target_device,
                                         self._SUPER_ROOT_MOUNT_POINT])
        ssh.remote_execute(self.dev_ip, ["mount", self._SUPER_ROOT_MOUNT_POINT +
                                         "rootfs",
                                         self._ROOT_PARTITION_MOUNT_POINT])

    def _install_tester_public_key(self, image_file_name):
        """
        Copy ssh public key to root user on the target device.

        Returns:
            None
        """
        # update info about the partition table
        if not self._uses_hddimg:
            self._mount_single_layer(image_file_name)
        else:
            self._mount_two_layers()

        # Identify the home of the root user
        root_user_home = ssh.remote_execute(
            self.dev_ip,
            [
                "cat",
                os.path.join(
                    self._ROOT_PARTITION_MOUNT_POINT,
                    "etc/passwd"),
                "|",
                "grep",
                "-e",
                '"^root"',
                "|",
                "sed",
                "-e",
                '"s/root:.*:root://"',
                "|",
                "sed", "-e",
                '"s/:.*//"']).rstrip().lstrip("/")

        # Ignore return value: directory might exist
        logger.info("Writing ssh-key to device.")
        ssh.remote_execute(
            self.dev_ip,
            [
                "mkdir",
                os.path.join(
                    self._ROOT_PARTITION_MOUNT_POINT,
                    root_user_home,
                    ".ssh")
            ],
            ignore_return_codes=[1])

        ssh.remote_execute(
            self.dev_ip,
            [
                "chmod",
                "700",
                os.path.join(
                    self._ROOT_PARTITION_MOUNT_POINT,
                    root_user_home,
                    ".ssh")
            ])

        ssh.remote_execute(
            self.dev_ip,
            [
                "cat",
                "~/.ssh/authorized_keys",
                ">>",
                os.path.join(
                    self._ROOT_PARTITION_MOUNT_POINT,
                    root_user_home,
                    ".ssh/authorized_keys")])

        ssh.remote_execute(
            self.dev_ip,
            [
                "chmod",
                "600",
                os.path.join(
                    self._ROOT_PARTITION_MOUNT_POINT,
                    root_user_home,
                    ".ssh/authorized_keys")
            ])

        if not self._uses_hddimg:
            logger.info("Adding IMA attribute to the ssh-key")
            ssh.remote_execute(
                self.dev_ip,
                [
                    "setfattr",
                    "-n",
                    "security.ima",
                    "-v",
                    "0x01`sha1sum " +
                    os.path.join(
                        self._ROOT_PARTITION_MOUNT_POINT,
                        root_user_home,
                        ".ssh/authorized_keys") + " | cut '-d ' -f1`",
                    os.path.join(
                        self._ROOT_PARTITION_MOUNT_POINT,
                        root_user_home,
                        ".ssh/authorized_keys")
                ])

        logger.info("Flushing.")
        ssh.remote_execute(self.dev_ip, ["sync"])

        logger.info("Unmounting.")
        ssh.remote_execute(
            self.dev_ip, ["umount", self._ROOT_PARTITION_MOUNT_POINT])

    def execute(self, command, timeout, user="root", verbose=False):
        """
        Runs a command on the device and returns log and errorlevel.

        Args:
            command (str): The command that will be executed
            timeout (integer): Timeout for the command
            user (str): The user that executes the command
            verbose (boolean): Controls verbosity

        Return:
            Return value of aft.ssh.remote_execute
        """
        return ssh.remote_execute(
            self.get_ip(),
            command,
            timeout=timeout,
            user=user)

    def push(self, source, destination, user="root"):
        """
        Deploys a file from the local filesystem to the device (remote).

        Args:
            source (str): The source file
            destination (str): The destination file
            user (str): The user who executes the command
        """
        ssh.push(self.get_ip(), source=source,
                 destination=destination, user=user)


    def check_poweron(self):
        """
        Check that PEM can be connected into. The device powers PEM, so this
        is a good sign that the device is powered on

        Returns:
            None

        Raises:
            aft.errors.AFTConfigurationError if device fails to power on
        """

        self._power_cycle()

        attempts = 2
        attempt_timeout = 60

        try:
            self._send_PEM_keystrokes(
                self._config_check_keystrokes,
                attempts=attempts,
                timeout=attempt_timeout)
        except errors.AFTDeviceError:
            raise errors.AFTConfigurationError(
                "Could not connect to PEM - check power and pem settings and " +
                "connections")

    def check_connection(self):
        """
        Boot into service mode, and check if ssh connection can be established

        Returns:
            None

        Raises:
            aft.errors.AFTConfigurationError on timeout

        """

        # set the retry count to lower value, as otherwise on failing device
        # this stage can take up to 2*retry_count*boot timeout seconds
        # (with values 8 and 240 that would be 3840 seconds or 64 minutes!)

        # retry count should be > 1 so that the occasional failed boot won't
        # fail the test
        self._RETRY_ATTEMPTS = 3

        # run in a process, as pem itself has no timeout and if there is a
        # connection or configuration issue, it will get stuck.

        # Queue is used to pass any exceptions from the subprocess back to main
        # process

        exception_queue = Queue()

        def invoker(exception_queue):
            """
            Helper function for process invocation.

            Attempts to enter service mode, and catches any exceptions and
            puts them in a Queue

            Args:
                exception_queue (multiprocessing.Queue):
                    The queue used to return the exceptions back to the main
                    process

            Returns:
                None
            """
            try:
                self._enter_mode(self._service_mode)
            except KeyboardInterrupt:
                pass
            except Exception as error:
                exception_queue.put(error)

        process = Process(target=invoker, args=(exception_queue,))
        process.start()
        process.join(1.5*self._RETRY_ATTEMPTS*self._BOOT_TIMEOUT)

        if process.is_alive():
            process.terminate()
            raise errors.AFTConfigurationError(
                "Timeout - PEM likely failed to connect")

        if not exception_queue.empty():
            raise exception_queue.get()

        logger.info("Succesfully booted device into service mode")


    def check_poweroff(self):
        """
        Check that PEM is offline by checking that the PEM process is still
        alive after a timeout (failed to connect and send the keystrokes)

        Returns:
            None

        Raises:
            aft.errors.AFTConfigurationError if PEM process has terminated
            before the timeout
        """

        # run Device class power of tests as well
        super(PCDevice, self).check_poweroff()



        try:
            self._send_PEM_keystrokes(
                self._config_check_keystrokes,
                timeout=20)
        except errors.AFTDeviceError as err:
            return


        raise errors.AFTConfigurationError(
            "Device seems to have failed to shut down - " +
            "PEM is still accessible")




# pylint: enable=too-many-instance-attributes
