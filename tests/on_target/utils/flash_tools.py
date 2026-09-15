##########################################################################################
# Copyright (c) 2024 Nordic Semiconductor
# SPDX-License-Identifier: LicenseRef-Nordic-5-Clause
##########################################################################################

import subprocess
import os
import sys
import glob
import time
sys.path.append(os.getcwd())
from utils.logger import get_logger
from utils.nrf91_flasher import nrf91_flasher
from pyocd.core.exceptions import TransferFaultError

logger = get_logger()

RESET_RETRIES = 3
RESET_RETRY_DELAY_S = 2

SEGGER = os.getenv('SEGGER')
RUNNER_DEVICE_TYPE = os.getenv('RUNNER_DEVICE_TYPE')
PROBE_TYPE = "JLINK"  # Default probe type

if RUNNER_DEVICE_TYPE in ["thingy91", "thingy91x"]:
    PROBE_TYPE = "PYOCD"

def reset_device(serial=SEGGER):
    if PROBE_TYPE == "JLINK":
        reset_device_jlink(serial)
    else:
        reset_device_pyocd(serial)

def flash_device(hexfile, serial=SEGGER):
    if PROBE_TYPE == "JLINK":
        flash_device_jlink(hexfile, serial)
    else:
        flash_device_pyocd(hexfile, serial)

def recover_device(serial=SEGGER):
    if PROBE_TYPE == "JLINK":
        recover_device_jlink(serial)
    else:
        recover_device_pyocd(serial)

def reset_device_pyocd(serial=SEGGER):
    # The device may be mid-write to internal flash (e.g. an in-progress FOTA
    # download) when a reset is requested, which can make pyOCD's memory
    # access to the target fault transiently. Retry a few times before giving up.
    for attempt in range(1, RESET_RETRIES + 1):
        try:
            nrf91_flasher(uid=serial)
            return
        except TransferFaultError as e:
            if attempt == RESET_RETRIES:
                raise
            logger.warning(
                f"pyOCD transfer fault while resetting device (attempt {attempt}/{RESET_RETRIES}): {e}. Retrying..."
            )
            time.sleep(RESET_RETRY_DELAY_S)

def flash_device_pyocd(hexfile, serial=SEGGER):
    nrf91_flasher(uid=serial, program=hexfile)

def recover_device_pyocd(serial=SEGGER):
    nrf91_flasher(uid=serial, erase=True)

def reset_device_jlink(serial=SEGGER, reset_kind="RESET_SYSTEM"):
    logger.info(f"Resetting device, segger: {serial}")
    try:
        result = subprocess.run(
            ['nrfutil', 'device', 'reset', '--serial-number', serial, '--reset-kind', reset_kind],
            check=True,
            text=True,
            capture_output=True
        )
        logger.info("Command completed successfully.")
    except subprocess.CalledProcessError as e:
        # Handle errors in the command execution
        logger.info("An error occurred while resetting the device.")
        logger.info("Error output:")
        logger.info(e.stderr)
        raise

def flash_device_jlink(hexfile, serial=SEGGER, extra_args=[]):
    # hexfile (str): Full path to file (hex or zip) to be programmed
    if not isinstance(hexfile, str):
        raise ValueError("hexfile cannot be None")
    logger.info(f"Flashing device, segger: {serial}, firmware: {hexfile}")
    try:
        result = subprocess.run(['nrfutil', 'device', 'program', *extra_args, '--firmware', hexfile, '--serial-number', serial], check=True, text=True, capture_output=True)
        logger.info("Command completed successfully.")
    except subprocess.CalledProcessError as e:
        # Handle errors in the command execution
        logger.info("An error occurred while flashing the device.")
        logger.info("Error output:")
        logger.info(e.stderr)
        raise

    reset_device_jlink(serial)

def recover_device_jlink(serial=SEGGER, core="Application"):
    logger.info(f"Recovering device, segger: {serial}")
    try:
        result = subprocess.run(['nrfutil', 'device', 'recover', '--serial-number', serial, '--core', core], check=True, text=True, capture_output=True)
        logger.info("Command completed successfully.")
    except subprocess.CalledProcessError as e:
        # Handle errors in the command execution
        logger.info("An error occurred while recovering the device.")
        logger.info("Error output:")
        logger.info(e.stderr)
        raise

def get_first_artifact_match(pattern):
    matches = glob.glob(pattern)
    if matches:
        return matches[0]
    else:
        return None
