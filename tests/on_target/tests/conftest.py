import os
import re
import pytest
import types
from utils.flash_tools import recover_device
from utils.uart import Uart, UartBinary
import sys
sys.path.append(os.getcwd())
from utils.logger import get_logger
from utils.nrfcloud import NRFCloud, NRFCloudFOTA

logger = get_logger()

UART_TIMEOUT = 60 * 30

SEGGER = os.getenv('SEGGER')
UART_ID = os.getenv('UART_ID', SEGGER)
DEVICE_UUID = os.getenv('UUID')
DEVICE_IMEI = os.getenv('IMEI')
NRFCLOUD_API_KEY = os.getenv('NRFCLOUD_API_KEY')
RUNNER_DEVICE_TYPE = os.getenv('RUNNER_DEVICE_TYPE')
ARTIFACT_PATH = os.getenv('ARTIFACT_PATH')
STAGE = os.getenv('STAGE')

TRACEPORT_INDEX = 1

if RUNNER_DEVICE_TYPE == "nrf9160dk":
    TRACEPORT_INDEX = 2

if RUNNER_DEVICE_TYPE in ["thingy91", "thingy91x"]:
    HEX_FILE_NAME = "zephyr.signed.hex"
else:
    HEX_FILE_NAME = "merged.hex"

def pytest_itemcollected(item):
    item._nodeid = f"{RUNNER_DEVICE_TYPE}::{STAGE}::{item._nodeid}"

def get_uarts():
    base_path = "/dev/serial/by-id"
    try:
        serial_paths = [os.path.join(base_path, entry) for entry in os.listdir(base_path)]
    except (FileNotFoundError, PermissionError) as e:
        raise RuntimeError("Failed to list serial devices") from e
    if not UART_ID:
        raise RuntimeError("UART_ID not set")
    uarts = [x for x in sorted(serial_paths) if UART_ID in x]
    return uarts

def scan_log_for_assertions(log):
    assert_counts = log.count("ASSERT")
    if assert_counts > 0:
        pytest.fail(f"{assert_counts} ASSERT found in log: {log}")

@pytest.hookimpl(tryfirst=True)
def pytest_runtest_logstart(nodeid, location):
    logger.info(f"Starting test: {nodeid}")

@pytest.hookimpl(trylast=True)
def pytest_runtest_logfinish(nodeid, location):
    logger.info(f"Finished test: {nodeid}")

@pytest.fixture(scope="function")
def dut_board(request):
    all_uarts = get_uarts()
    if not all_uarts:
        pytest.fail("No UARTs found")
    log_uart_string = all_uarts[0]
    uart = Uart(log_uart_string, timeout=UART_TIMEOUT)
    modem_traces_uart = UartBinary(all_uarts[TRACEPORT_INDEX], timeout=UART_TIMEOUT)

    yield types.SimpleNamespace(
        uart=uart,
        device_type=RUNNER_DEVICE_TYPE,
        imei=DEVICE_IMEI
    )

    uart_log = uart.whole_log
    uart.stop()

    scan_log_for_assertions(uart_log)

    sample_name = request.node.name
    modem_traces_uart.stop()
    modem_traces_uart.save_to_file(os.path.join("outcomes/", f"trace_{sample_name}.bin"))

@pytest.fixture(scope="function")
def dut_cloud(dut_board):
    if not NRFCLOUD_API_KEY:
        pytest.skip("NRFCLOUD_API_KEY environment variable not set")
    if not DEVICE_UUID:
        pytest.skip("UUID environment variable not set")

    cloud = NRFCloud(api_key=NRFCLOUD_API_KEY)
    device_id = DEVICE_UUID

    yield types.SimpleNamespace(
        **dut_board.__dict__,
        cloud=cloud,
        device_id=device_id,
    )

@pytest.fixture(scope="function")
def dut_fota(dut_board):
    if not NRFCLOUD_API_KEY:
        pytest.skip("NRFCLOUD_API_KEY environment variable not set")
    if not DEVICE_UUID:
        pytest.skip("UUID environment variable not set")

    fota = NRFCloudFOTA(api_key=NRFCLOUD_API_KEY)
    device_id = DEVICE_UUID
    data = {
        'job_id': '',
    }
    fota.cancel_incomplete_jobs(device_id)

    yield types.SimpleNamespace(
        **dut_board.__dict__,
        fota=fota,
        device_id=device_id,
        data=data
    )
    fota.cancel_incomplete_jobs(device_id)

def find_hex_file(test_name):
    potential_path = os.path.join(ARTIFACT_PATH, f"{RUNNER_DEVICE_TYPE}-{test_name}/{HEX_FILE_NAME}")
    if os.path.isfile(potential_path):
        return potential_path

@pytest.fixture(scope="session")
def coap_device_message_hex_file():
    return find_hex_file("nrf_cloud_coap_device_message") or pytest.skip("HEX file not found")

@pytest.fixture(scope="session")
def coap_cell_location_hex_file():
    return find_hex_file("nrf_cloud_coap_cell_location") or pytest.skip("HEX file not found")

@pytest.fixture(scope="session")
def coap_fota_hex_file():
    return find_hex_file("nrf_cloud_coap_fota") or pytest.skip("HEX file not found")

@pytest.fixture(scope="session")
def coap_fota_fmfu_hex_file():
    # just skip if HEX file not found, thingy91 doesn't have support for fmfu because of missing external flash
    return find_hex_file("nrf_cloud_coap_fota_fmfu") or pytest.skip("HEX file not found")

@pytest.fixture(scope="session")
def coap_fota_test_zip_file():
    for test_name in ["nrf_cloud_coap_fota_test", "nrf_cloud_coap_fota_fmfu"]:
        potential_path = os.path.join(ARTIFACT_PATH, f"{RUNNER_DEVICE_TYPE}-{test_name}/dfu_application.zip")
        if os.path.isfile(potential_path):
            return potential_path
    pytest.skip("ZIP file not found")

@pytest.fixture(scope="session")
def rest_device_message_hex_file():
    return find_hex_file("nrf_cloud_rest_device_message") or pytest.skip("HEX file not found")

@pytest.fixture(scope="session")
def rest_cell_location_hex_file():
    return find_hex_file("nrf_cloud_rest_cell_location") or pytest.skip("HEX file not found")

@pytest.fixture(scope="session")
def rest_fota_hex_file():
    return find_hex_file("nrf_cloud_rest_fota") or pytest.skip("HEX file not found")

@pytest.fixture(scope="session")
def rest_fota_fmfu_hex_file():
    # just skip if HEX file not found, thingy91 doesn't have support for fmfu because of missing external flash
    return find_hex_file("nrf_cloud_rest_fota_fmfu") or pytest.skip("HEX file not found")

@pytest.fixture(scope="session")
def rest_fota_test_zip_file():
    for test_name in ["nrf_cloud_rest_fota_test", "nrf_cloud_rest_fota_fmfu"]:
        potential_path = os.path.join(ARTIFACT_PATH, f"{RUNNER_DEVICE_TYPE}-{test_name}/dfu_application.zip")
        if os.path.isfile(potential_path):
            return potential_path
    pytest.skip("ZIP file not found")

@pytest.fixture(scope="session")
def mqtt_device_message_hex_file():
    return find_hex_file("nrf_cloud_mqtt_device_message") or pytest.skip("HEX file not found")

@pytest.fixture(scope="session")
def mqtt_cell_location_hex_file():
    return find_hex_file("nrf_cloud_mqtt_cell_location") or pytest.skip("HEX file not found")

@pytest.fixture(scope="session")
def mqtt_fota_hex_file():
    return find_hex_file("nrf_cloud_mqtt_fota") or pytest.skip("HEX file not found")

@pytest.fixture(scope="session")
def mqtt_fota_fmfu_hex_file():
    # just skip if HEX file not found, thingy91 doesn't have support for fmfu because of missing external flash
    return find_hex_file("nrf_cloud_mqtt_fota_fmfu") or pytest.skip("HEX file not found")

@pytest.fixture(scope="session")
def mqtt_fota_test_zip_file():
    for test_name in ["nrf_cloud_mqtt_fota_test", "nrf_cloud_mqtt_fota_fmfu"]:
        potential_path = os.path.join(ARTIFACT_PATH, f"{RUNNER_DEVICE_TYPE}-{test_name}/dfu_application.zip")
        if os.path.isfile(potential_path):
            return potential_path
    pytest.skip("ZIP file not found")

@pytest.fixture(scope="session")
def memfault_hex_file():
    return find_hex_file("memfault_sample") or pytest.skip("HEX file not found")
