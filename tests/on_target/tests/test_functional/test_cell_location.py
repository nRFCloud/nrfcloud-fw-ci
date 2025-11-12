import os
import pytest
import time
import sys
sys.path.append(os.getcwd())
from utils.logger import get_logger
from utils.flash_tools import flash_device, reset_device

logger = get_logger()

CLOUD_TIMEOUT = 60 * 3

@pytest.mark.cell_location
def test_coap_cell_location(dut_cloud, coap_cell_location_hex_file):
    '''
    Test that verifies that device can connect to nRF Cloud CoAP and request cell location.
    '''

    flash_device(os.path.abspath(coap_cell_location_hex_file))
    dut_cloud.uart.xfactoryreset()
    dut_cloud.uart.flush()

    test_start_time = time.time()
    reset_device()

    dut_cloud.uart.wait_for_str_ordered(
        [
            "Connected to network",
            "nrf_cloud_coap_transport: Authorized",
            "Current cell info: Cell ID: ",
            "nrf_cloud_coap_cell_location_sample: Lat:"
        ],
        timeout=CLOUD_TIMEOUT
    )

    # Poll for location to be reported to cloud
    start = time.time()
    while time.time() - start < CLOUD_TIMEOUT:
        time.sleep(5)
        locations = dut_cloud.cloud.get_location_history(dut_cloud.device_id, max_records=20, start=test_start_time)
        logger.debug(f"Found locations: {locations}")
        if len(locations) > 0:
            break
    else:
        raise RuntimeError("No new locations observed")

@pytest.mark.cell_location
def test_rest_cell_location(dut_cloud, rest_cell_location_hex_file):
    '''
    Test that verifies that device can connect to nRF Cloud and request cell location.
    '''

    flash_device(os.path.abspath(rest_cell_location_hex_file))
    dut_cloud.uart.xfactoryreset()
    dut_cloud.uart.flush()

    test_start_time = time.time()
    reset_device()

    dut_cloud.uart.wait_for_str_ordered(
        [
            "Connected to network",
            "Current cell info: Cell ID: ",
            "nrf_cloud_rest_cell_location_sample: Lat:"
        ],
        timeout=CLOUD_TIMEOUT
    )

    # Poll for location to be reported to cloud
    start = time.time()
    while time.time() - start < CLOUD_TIMEOUT:
        time.sleep(5)
        locations = dut_cloud.cloud.get_location_history(dut_cloud.device_id, max_records=20, start=test_start_time)
        logger.debug(f"Found locations: {locations}")
        if len(locations) > 0:
            break
    else:
        raise RuntimeError("No new locations observed")
