import os
import pytest
import time
import sys
import re
import functools
sys.path.append(os.getcwd())
from utils.logger import get_logger
from utils.flash_tools import flash_device, reset_device

logger = get_logger()

CLOUD_TIMEOUT = 60 * 10
FMFU_TIMEOUT = 60 * 60

ARTIFACT_VERSION = os.getenv('ARTIFACT_VERSION')
APP_BUNDLEID = os.getenv("APP_BUNDLEID", None)

supported_mfw_versions = {
    "mfw_nrf9160_1.3.6" : {
        "new_version_delta" : "mfw_nrf9160_1.3.6-FOTA-TEST",
        "new_version_full" : "mfw_nrf9160_1.3.7",
    },
    "mfw_nrf9160_1.3.6-FOTA-TEST" : {
        "new_version_delta" : "mfw_nrf9160_1.3.6",
        "new_version_full" : "mfw_nrf9160_1.3.7",
    },
    "mfw_nrf9160_1.3.7" : {
        "new_version_delta" : "mfw_nrf9160_1.3.7-FOTA-TEST",
        "new_version_full" : "mfw_nrf9160_1.3.6",
    },
    "mfw_nrf9160_1.3.7-FOTA-TEST" : {
        "new_version_delta" : "mfw_nrf9160_1.3.7",
        "new_version_full" : "mfw_nrf9160_1.3.6",
    },
    "mfw_nrf91x1_2.0.2" : {
        "new_version_delta" : "mfw_nrf91x1_2.0.2-FOTA-TEST",
        "new_version_full" : "mfw_nrf91x1_2.0.3",
    },
    "mfw_nrf91x1_2.0.2-FOTA-TEST" : {
        "new_version_delta" : "mfw_nrf91x1_2.0.2",
        "new_version_full" : "mfw_nrf91x1_2.0.3",
    },
    "mfw_nrf91x1_2.0.3" : {
        "new_version_delta" : "mfw_nrf91x1_2.0.3-FOTA-TEST",
        "new_version_full" : "mfw_nrf91x1_2.0.2",
    },
    "mfw_nrf91x1_2.0.3-FOTA-TEST" : {
        "new_version_delta" : "mfw_nrf91x1_2.0.3",
        "new_version_full" : "mfw_nrf91x1_2.0.2",
    },
}

def await_nrfcloud(func, expected, field, timeout, break_value="CANCELLED"):
    start = time.time()
    logger.info(f"Awaiting {field} == {expected} in nrfcloud shadow...")
    while True:
        time.sleep(5)
        if time.time() - start > timeout:
            raise RuntimeError(f"Timeout awaiting {field} update")
        try:
            data = func()
        except Exception as e:
            logger.warning(f"Exception {e} during waiting for {field}")
            continue
        logger.debug(f"Reported {field}: {data}")
        if data == break_value:
            raise RuntimeError(f"{field} changed to unexpected value: {break_value}")
        if expected in data:
            break

def get_appversion(dut_fota):
    shadow = dut_fota.fota.get_device(dut_fota.device_id)
    return shadow["state"]["reported"]["device"]["deviceInfo"]["appVersion"]

def get_modemversion(dut_fota):
    shadow = dut_fota.fota.get_device(dut_fota.device_id)
    return shadow["state"]["reported"]["device"]["deviceInfo"]["modemFirmware"]

def setup_fota_sample(dut_fota, hex_file):
    flash_device(os.path.abspath(hex_file))
    dut_fota.uart.xfactoryreset()
    dut_fota.uart.flush()

    test_start_time = time.time()
    reset_device()

    dut_fota.uart.wait_for_str_ordered(
        [
            "Connected to LTE",
            "nrf_cloud_info: Modem FW:"
        ],
        timeout=CLOUD_TIMEOUT
    )

def parse_mfw_version_from_log(log):
    for match in re.finditer(r"Modem FW:\s+(mfw_nrf9..._\d\.\d\.\d(-FOTA-TEST)?)", log, re.MULTILINE):
        return match.group(1)

def perform_any_fota(dut_fota, bundle_id, timeout=CLOUD_TIMEOUT):
    try:
        dut_fota.data['job_id'] = dut_fota.fota.create_fota_job(dut_fota.device_id, bundle_id)
        dut_fota.data['bundle_id'] = bundle_id
    except Exception as e:
        pytest.fail(f"FOTA create_job REST API error: {e}")
    logger.info(f"Created FOTA Job (ID: {dut_fota.data['job_id']})")

    logger.info("Waiting for FOTA to start...")
    await_nrfcloud(
        functools.partial(dut_fota.fota.get_fota_status, dut_fota.data['job_id']),
        "IN_PROGRESS",
        "FOTA status",
        timeout
    )

    reset_device()

    logger.info("Waiting for FOTA to complete...")
    await_nrfcloud(
        functools.partial(dut_fota.fota.get_fota_status, dut_fota.data['job_id']),
        "COMPLETED",
        "FOTA status",
        timeout
    )

def test_coap_mfw_delta_fota(dut_fota, coap_fota_hex_file):
    '''
    Test that verifies that device can connect to nRF Cloud CoAP and perform MFW delta FOTA update.
    '''

    setup_fota_sample(dut_fota, coap_fota_hex_file)

    dut_fota.uart.wait_for_str("nrf_cloud_coap_transport: Authorized")

    current_version = parse_mfw_version_from_log(dut_fota.uart.whole_log)

    if not current_version:
        raise RuntimeError(f"Failed to find current modem FW version")

    if current_version in supported_mfw_versions:
        new_version = supported_mfw_versions[current_version]["new_version_delta"]
        bundle_id = dut_fota.fota.get_mfw_delta_bundle_id(current_version, new_version)
    else:
        raise RuntimeError(f"Unexpected starting modem FW version: {current_version}")

    perform_any_fota(dut_fota, bundle_id)

    logger.info("Verifying new modem FW version...")
    await_nrfcloud(
        functools.partial(get_modemversion, dut_fota),
        new_version,
        "modemFirmware",
        CLOUD_TIMEOUT
    )

def test_rest_mfw_delta_fota(dut_fota, rest_fota_hex_file):
    '''
    Test that verifies that device can connect to nRF Cloud REST and perform MFW delta FOTA update.
    '''

    setup_fota_sample(dut_fota, rest_fota_hex_file)

    current_version = parse_mfw_version_from_log(dut_fota.uart.whole_log)

    if not current_version:
        raise RuntimeError(f"Failed to find current modem FW version")

    if current_version in supported_mfw_versions:
        new_version = supported_mfw_versions[current_version]["new_version_delta"]
        bundle_id = dut_fota.fota.get_mfw_delta_bundle_id(current_version, new_version)
    else:
        raise RuntimeError(f"Unexpected starting modem FW version: {current_version}")

    perform_any_fota(dut_fota, bundle_id)

    logger.info("Verifying new modem FW version...")
    await_nrfcloud(
        functools.partial(get_modemversion, dut_fota),
        new_version,
        "modemFirmware",
        CLOUD_TIMEOUT
    )

@pytest.mark.slow
def test_coap_mfw_full_fota(dut_fota, coap_fota_fmfu_hex_file):
    '''
    Test that verifies that device can connect to nRF Cloud CoAP and perform MFW full FOTA update.
    '''

    setup_fota_sample(dut_fota, coap_fota_fmfu_hex_file)

    dut_fota.uart.wait_for_str("nrf_cloud_coap_transport: Authorized")

    current_version = parse_mfw_version_from_log(dut_fota.uart.whole_log)

    if not current_version:
        raise RuntimeError(f"Failed to find current modem FW version")

    if current_version in supported_mfw_versions:
        new_version = supported_mfw_versions[current_version]["new_version_full"]
        bundle_id = dut_fota.fota.get_mfw_full_bundle_id(new_version)
    else:
        raise RuntimeError(f"Unexpected starting modem FW version: {current_version}")

    perform_any_fota(dut_fota, bundle_id, timeout=FMFU_TIMEOUT)

    logger.info("Verifying new modem FW version...")
    await_nrfcloud(
        functools.partial(get_modemversion, dut_fota),
        new_version,
        "modemFirmware",
        CLOUD_TIMEOUT
    )


@pytest.mark.slow
def test_rest_mfw_full_fota(dut_fota, rest_fota_fmfu_hex_file):
    '''
    Test that verifies that device can connect to nRF Cloud REST and perform MFW full FOTA update.
    '''

    setup_fota_sample(dut_fota, rest_fota_fmfu_hex_file)

    current_version = parse_mfw_version_from_log(dut_fota.uart.whole_log)

    if not current_version:
        raise RuntimeError(f"Failed to find current modem FW version")

    if current_version in supported_mfw_versions:
        new_version = supported_mfw_versions[current_version]["new_version_full"]
        bundle_id = dut_fota.fota.get_mfw_full_bundle_id(new_version)
    else:
        raise RuntimeError(f"Unexpected starting modem FW version: {current_version}")

    perform_any_fota(dut_fota, bundle_id, timeout=FMFU_TIMEOUT)

    logger.info("Verifying new modem FW version...")
    await_nrfcloud(
        functools.partial(get_modemversion, dut_fota),
        new_version,
        "modemFirmware",
        CLOUD_TIMEOUT
    )

def test_coap_app_fota(dut_fota, coap_fota_hex_file, coap_fota_test_zip_file):
    '''
    Test that verifies that device can connect to nRF Cloud CoAP and perform application FOTA update.
    '''

    bundle_id = dut_fota.fota.upload_zephyr_zip(
        zip_path=coap_fota_test_zip_file,
        version="1.0.0-fotatest",
        name=ARTIFACT_VERSION
    )

    setup_fota_sample(dut_fota, coap_fota_hex_file)

    dut_fota.uart.wait_for_str("nrf_cloud_coap_transport: Authorized")

    try:
        perform_any_fota(dut_fota, bundle_id)
    except Exception as e:
        raise e
    finally:
        dut_fota.fota.delete_bundle(bundle_id)

    if "1.0.0-fotatest" not in dut_fota.uart.whole_log:
        raise RuntimeError("Couldn't verify that correct APP is running after FOTA")

def test_rest_app_fota(dut_fota, rest_fota_hex_file, rest_fota_test_zip_file):
    '''
    Test that verifies that device can connect to nRF Cloud REST and perform application FOTA update.
    '''

    bundle_id = dut_fota.fota.upload_zephyr_zip(
        zip_path=rest_fota_test_zip_file,
        version="1.0.0-fotatest",
        name=ARTIFACT_VERSION
    )

    setup_fota_sample(dut_fota, rest_fota_hex_file)

    try:
        perform_any_fota(dut_fota, bundle_id)
    except Exception as e:
        raise e
    finally:
        dut_fota.fota.delete_bundle(bundle_id)

    if "1.0.0-fotatest" not in dut_fota.uart.whole_log:
        raise RuntimeError("Couldn't verify that correct APP is running after FOTA")

#TODO: bootloader FOTA
