import os
import pytest
import time
from datetime import datetime, timezone
import sys
import re
import functools
sys.path.append(os.getcwd())
from utils.logger import get_logger
from utils.flash_tools import flash_device, reset_device
from utils import memfault as mflt
import dateutil

logger = get_logger()

CLOUD_TIMEOUT = 60 * 10

ARTIFACT_VERSION = os.getenv('ARTIFACT_VERSION')

def get_latest(family_type, device_id, start_time):
    if family_type == "reboot":
        return mflt.get_latest_reboot_events(device_id, start_time)
    elif family_type == "heartbeat":
        return mflt.get_latest_heartbeat_events(device_id, start_time)
    elif family_type == "log_capture":
        return mflt.get_latest_logs(device_id)
    elif family_type == "trace":
        return mflt.get_latest_traces(device_id)
    elif family_type == "coredump":
        return mflt.get_latest_coredump_traces(device_id)

def timestamp(upload):
    return dateutil.parser.parse(upload.get("captured_date") or upload["event_data"]["received_event"]["captured_date"])

    # Instruct memfault library to create and upload either event, coredump, log
def check_upload(uart, device_id, family, start_time):
    latest_uploads = get_latest(family, device_id)
    if latest_uploads:
        timestamp_old_upload = timestamp(latest_uploads[0])
    else:
        timestamp_old_upload = None

    uart.flush()

    if family in ["reboot"]:
        uart.write(f"mflt test {family}\r\n".encode())
    if family in ["log_capture"]:
        uart.write("mflt test logs\r\n".encode())
        uart.wait_for_str(["Raw log!", "memfault_platform_log: Debug log!", "Info log!", "Warning log", "Error log"], MFLT_TIMEOUT)
        uart.write(f"mflt test {family}\r\n".encode())
        uart.write("mflt post_chunks\r\n".encode())
    if family in ["heartbeat", "trace"]:
        uart.write(f"mflt test {family}\r\n".encode())
        uart.write("mflt post_chunks\r\n".encode())
    elif family == "coredump":
        uart.write("mflt test usagefault\r\n".encode())

    # Wait for reboot to happen correctly
    if family in ["reboot", "coredump"]:
        uart.wait_for_str(["Connected to network"], CLOUD_TIMEOUT)

    # Wait for upload to be reported to memfault api
    start = time.time()
    while time.time() - start < CLOUD_TIMEOUT:
        time.sleep(5)
        new_uploads = get_latest(family, device_id)
        if not new_uploads:
            continue
        # Check that we have an upload with newer timestamp
        if not timestamp_old_upload:
            break
        if timestamp(new_uploads[0]) > timestamp_old_upload:
            break
    else:
        raise RuntimeError(f"No new {family} observed")

    # Check that the new upload is less than 10 mins old
    new_upload = new_uploads[0]
    max_age = datetime.timedelta(minutes=10)
    now = datetime.datetime.now(datetime.timezone.utc)
    assert timestamp(new_upload) > (now - max_age)


@pytest.mark.memfault
def test_memfault(dut_board, memfault_hex_file):
    flash_device(os.path.abspath(memfault_hex_file))
    dut_board.uart.xfactoryreset()
    dut_board.uart.flush()

    test_start_time = datetime.now(timezone.utc)
    reset_device()

    dut_board.uart.write("mflt get_device_info\r\n".encode())
    dut_board.uart.wait_for_str([f"S/N: 359", "SW type:", "SW version:", "HW version:"], CLOUD_TIMEOUT)

    dut_board.uart.write("mflt clear_core\r\n".encode())
    dut_board.uart.wait_for_str(["Invalidating coredump"], CLOUD_TIMEOUT)

    dut_board.uart.write("mflt get_core\r\n".encode())
    dut_board.uart.wait_for_str(["No coredump present!"], CLOUD_TIMEOUT)

    check_upload(dut_board.uart, dut_board.imei, "reboot", test_start_time)