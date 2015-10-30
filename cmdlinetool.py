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
Abstract Model of a Command Line tool.
"""

import abc
import sys
import logging
import subprocess32
import multiprocessing

from collections import namedtuple

VERSION = "0.1.0"

CmdResult = namedtuple("CmdResult", "returncode, stdoutdata, stderrdata")

# pylint: disable=too-few-public-methods
class CmdLineTool(object):
    """
    Abstract Base Class for wrapping cmdline tools.
    """
    __metaclass__ = abc.ABCMeta
    DEFAULT_TIMEOUT = 10

    @classmethod
    def init_class(cls, command=None, timeout=DEFAULT_TIMEOUT,
                   exit_on_error=False):
        """
        Init function for class variables.
        """
        cls.command = command
        cls._exit_on_error = exit_on_error
        cls._timeout = timeout
        return cls._probe_command()

    @classmethod
    def _probe_command(cls):
        """
        Tests if a certain shell command is available.
        Can either return error or throw an exception.
        """
        logging.info("Testing for presence of \"{0}\" command."
                     .format(cls.command))
        try:
            subprocess32.check_output(["which", cls.command],
                                    stderr=subprocess32.STDOUT)
            logging.info("Command {0} found.".format(cls.command))
            return True
        except subprocess32.CalledProcessError:
            logging.critical("Error: cannot locate {0} command."
                             .format(cls.command))
            if cls._exit_on_error:
                sys.exit(-1)
            return False

    @classmethod
    def _run(cls, parms=(), timeout=-1, verbose=False):
        """
        Runs the command in a separate thread, with timeout.
        """
        result_q = multiprocessing.Queue()
        result = None
        process = multiprocessing.Process(target=_runner,
                                          args=[cls.command, parms,
                                                result_q, verbose])
        timeout = cls._timeout if timeout == -1 else timeout
        try:
            process.start()
            process.join(timeout=timeout)
            if process.is_alive():
                process.terminate()
                process.join()
            else:
                result = result_q.get()
        except multiprocessing.TimeoutError:
            logging.warn("Command timedout:"
                         "{0} {1}".format(cls.command, parms))
        if cls._exit_on_error and result is None:
            sys.exit(-1)
        return result


def _runner(command, parms, result_q, verbose=False):
    """
    Executes the command with the given parameters.
    It's meant to run from a thread with timeout.
    """
    try:
        command = (command,) + parms
        if verbose:
            logging.debug("{0}".format(command))
        process = subprocess32.Popen(command,
                                   stderr=subprocess32.STDOUT,
                                   stdout=subprocess32.PIPE,)
        stdoutdata, stderrdata = process.communicate()
        result = CmdResult(returncode=process.returncode,
                           stdoutdata=stdoutdata,
                           stderrdata=stderrdata)
        if result.returncode != 0:
            logging.debug("Error running:\n{0}\n".format(command) +
                          "* returncode: {0}\n".format(result.returncode) +
                          "* stdout: {0}\n".format(result.stdoutdata) +
                          "* stderr: {0}\n".format(result.stderrdata))
    except OSError as error:
        result = CmdResult(returncode=error.errno, stdoutdata="",
                           stderrdata=error.strerror)
        logging.debug("OSError running:\n{0}\n".format(command) +
                      "* returncode: {0}\n".format(result.returncode) +
                      "* error message {0}\n".format(result.stderrdata))
    result_q.put(result)
# pylint: enable=too-few-public-methods
