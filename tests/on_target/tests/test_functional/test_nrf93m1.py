import os
import pytest
import time
import sys
import re
sys.path.append(os.getcwd())
from utils.logger import get_logger
from utils.flash_tools import flash_device, reset_device

logger = get_logger()

CLOUD_TIMEOUT = 30

def parse_uuid_from_log(log):
    for match in re.finditer(r"%DEVICEUUID: ([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})", log, re.MULTILINE):
        return match.group(1)

def wait_until_online(uart, timeout=30):
    start = time.time()
    log_index = len(uart.log)

    uart.at_cmd_write("AT+CFUN=1")
    # wait, but allow for interruption
    while not uart._evt.is_set():
        time.sleep(0.2)
        registered = False
        if "+CEREG: 5" in uart.log[log_index:]: # registered, roaming
            registered = True
            break
        if "+CEREG: 1" in uart.log[log_index:]: # registered, home network
            registered = True
            break
        if registered:
            uart.at_cmd_write("AT+COPS?")
            uart.at_cmd_write("AT+CCLK?")
            return
        if start + timeout < time.time():
            raise RuntimeError("wait for network timed out")

def check_for_handshake(uart):
    uart.wait_for_str_ordered(
        [
            "%COAP: CONNECTING",
            "%COAP: DTLS_STATE,4",
            "%COAP: SENDING_AUTH",
            "%COAP: RESPONSE,2.01",
            "%COAP: CONNECTED"
        ],
        timeout=CLOUD_TIMEOUT,
    )

def cell_location(uart):
    log_index = len(uart.log)
    uart.at_cmd_write("AT%NRFCLOUDLOCATION=1,1")
    check_for_handshake(uart)
    uart.wait_for_str_ordered(
        [
            "%COAP: RESPONSE,2.05",
            "%COAP: DATA,HEX,",
            "%NRFCLOUDLOCATION: 6"
        ],
        timeout=CLOUD_TIMEOUT,
        start=log_index
    )

def cloud_message(uart):
    log_index = len(uart.log)
    uart.at_cmd_write('AT%NRFCLOUDMESSAGE={"appId":"BUTTON","data":"1"}')
    check_for_handshake(uart)
    uart.wait_for_str_ordered(
        [
            "%NRFCLOUDMESSAGE: SENT"
        ],
        timeout=CLOUD_TIMEOUT,
        start=log_index
    )

def shadow_set(uart):
    log_index = len(uart.log)
    uart.at_cmd_write('AT%NRFCLOUDSHADOW=config.switch,true')
    check_for_handshake(uart)
    uart.wait_for_str_ordered(
        [
            "%COAP: RESPONSE,2.04"
        ],
        timeout=CLOUD_TIMEOUT,
        start=log_index
    )

@pytest.mark.nrf93m1
def test_nrf93m1_various(dut_cloud):
    reset_device()
    dut_cloud.uart.wait_for_str_ordered(
        [
            "RDY"
        ],
        timeout=CLOUD_TIMEOUT
    )

    if ("%NRFCLOUDOBS: coredump available" in dut_cloud.uart.whole_log):
        dut_cloud.uart.at_cmd_write("AT+NFWUPD=0")

    dut_cloud.uart.at_cmd_write("AT%DEVICEUUID")
    dut_cloud.uart.at_cmd_write("AT+CGMR")
    dut_cloud.uart.at_cmd_write("AT+CEREG=5")
    dut_cloud.uart.at_cmd_write("AT+CFUN=0")

    uuid = parse_uuid_from_log(dut_cloud.uart.whole_log)

    logger.info(f"device uuid: {uuid}")

    if dut_cloud.device_id != uuid:
        raise RuntimeError(f"expected uuid: {dut_cloud.device_id}")

    wait_until_online(dut_cloud.uart)

    cell_location(dut_cloud.uart)
    cell_location(dut_cloud.uart)
    cloud_message(dut_cloud.uart)
    cloud_message(dut_cloud.uart)
    shadow_set(dut_cloud.uart)
    shadow_set(dut_cloud.uart)

    dut_cloud.uart.at_cmd_write("AT+CFUN=0")

    wait_until_online(dut_cloud.uart)

    cell_location(dut_cloud.uart)
