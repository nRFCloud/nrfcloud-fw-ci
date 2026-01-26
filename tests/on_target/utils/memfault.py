#!/usr/bin/env python3
#
# Copyright (c) 2026 Nordic Semiconductor ASA
#
# SPDX-License-Identifier: LicenseRef-Nordic-5-Clause

import subprocess
import re
import requests
import os
import sys
from datetime import datetime, timedelta, timezone
sys.path.append(os.getcwd())
from utils.logger import get_logger

logger = get_logger()

username = ""
base_url = "https://api.memfault.com/api/v0"


_org = os.getenv("MEMFAULT_ORGANIZATION_SLUG")
if not _org:
    raise ValueError("MEMFAULT_ORGANIZATION_SLUG environment variable is required")

_proj = os.getenv("MEMFAULT_PROJECT_SLUG")
if not _proj:
    raise ValueError("MEMFAULT_PROJECT_SLUG environment variable is required")

org = f"organizations/{_org}"
proj = f"projects/{_proj}"

org_token = os.getenv("MEMFAULT_ORGANIZATION_TOKEN")
if not org_token:
    raise ValueError("MEMFAULT_ORGANIZATION_TOKEN environment variable is required")

project_token = os.getenv("MEMFAULT_PROJECT_KEY")
if not project_token:
    raise ValueError("MEMFAULT_PROJECT_KEY environment variable is required")

api_key = org_token

def get_device(device_serial: str) -> list:
    r = requests.get(
        f"{base_url}/{org}/{proj}/devices/{device_serial}",
        auth=(username, api_key), timeout=10
    )
    r.raise_for_status()
    return r.json()["data"]

def get_issues():
    r = requests.get(
        f"{base_url}/{org}/{proj}/issues",
        auth=(username, api_key), timeout=10
    )
    r.raise_for_status()
    return r.json()["data"]

def memfault_get_upload_params() -> list:
    r = requests.post(f"{base_url}/{org}/{proj}/upload", auth=(username, api_key), timeout=10)
    r.raise_for_status()
    return r.json()["data"]["upload_url"], r.json()["data"]["token"]

def get_gnu_build_id(path_to_elf: str):
    cmd = f"readelf -n {path_to_elf}".split()
    output = subprocess.check_output(cmd)
    m = re.search(b"Build ID: ([^ ]+)$", output)
    if m:
        return m.group(1).decode().strip()

def upload_elf(path_to_elf: str):
    gnu_id = get_gnu_build_id(path_to_elf)
    version = f"0.0.1+{gnu_id[0:6]}"

    cmd = f"""memfault --org-token {org_token} --org {_org} --project {_proj}
        upload-mcu-symbols 
        --software-type nrf91ns-fw 
        --software-version {version} 
        --revision {gnu_id} 
        {path_to_elf}""".split()
    a = subprocess.check_output(cmd)
    logger.info(a.decode())

def get_releases():
    r = requests.get(
        f"{base_url}/{org}/{proj}/releases",
        auth=(username, api_key), timeout=10
    )
    r.raise_for_status()
    return r.json()

def create_release(version, rev):
    r = requests.post(
        f"{base_url}/{org}/{proj}/releases",
        auth=(username, api_key),
        json={
            "version": version,
            "revision": rev
        }, timeout=10
    )
    r.raise_for_status()
    return r.json()

def delete_release(version):
    r = requests.delete(
        f"{base_url}/{org}/{proj}/releases/{version}",
        auth=(username, api_key), timeout=10
    )
    r.raise_for_status()

def get_issue(issue_id: int):
    r = requests.get(
        f"{base_url}/{org}/{proj}/issues/{issue_id}",
        auth=(username, api_key), timeout=10
    )
    r.raise_for_status()
    return r.json()

def get_issue_last_seen_timestamp(issue_id):
    issue = get_issue(issue_id)
    return issue["data"]["last_seen"]

def get_chronicler_events(
        device_serial=None,
        device_id=None,
        event_types=("ReceivedDataRebootEvent", "ReceivedDataHeartbeatEvent", "ReceivedDataTraceEvent"),
        levels=("INFO", "ERROR"),
        start=None, end=None
):
    if not start:
        start = datetime.now(timezone.utc) - timedelta(hours=1)
    if not end:
        end = datetime.now(timezone.utc)

    params = {
        "device_id": device_id,
        "device_serial": device_serial,
        "event_types": event_types,
        "levels": levels,
        "start": datetime.isoformat(start),
        "end": datetime.isoformat(end)
    }
    
    r = requests.get(
        f"{base_url}/{org}/{proj}/chronicler-logs",
        auth=(username, api_key),
        params=params,
        timeout=10
    )
    r.raise_for_status()

    logger.debug(f"Chronicler events params: {params}")
    logger.debug(f"Chronicler events response: {r.json()}")

    return r.json()["data"]

def get_latest_reboot_events(device_serial, start=None):
    return get_chronicler_events(
        device_serial=device_serial,
        event_types=["ReceivedDataRebootEvent"],
        start=start
    )
    
def get_latest_heartbeat_events(device_serial, start=None):
    return get_chronicler_events(
        device_serial=device_serial,
        event_types=["ReceivedDataHeartbeatEvent"],
        start=start
    )

def get_latest_logs(device_serial: str) -> list:
    r = requests.get(
        f"{base_url}/{org}/{proj}/devices/{device_serial}/log-files",
        auth=(username, api_key), timeout=10
    )
    r.raise_for_status()
    return r.json()["data"]

def get_latest_traces(device_serial):
    return get_traces("event", device_serial)

def get_latest_coredump_traces(device_serial):
    return get_traces("coredump", device_serial)

def get_traces(family, device_serial):
    r = requests.get(
        f"{base_url}/{org}/{proj}/traces",
        auth=(username, api_key), timeout=10
    )
    r.raise_for_status()
    data = r.json()["data"]
    latest_traces = [
        x
        for x in data
        if x["device"]["device_serial"] == str(device_serial) and x["source_type"] == family
    ]
    return latest_traces

def get_latest_coredumps(issue_id):
    r = requests.get(
        f"{base_url}/{org}/{proj}/coredumps",
        auth=(username, api_key), timeout=10
    )
    r.raise_for_status()
    data = r.json()["data"]
    latest_coredumps = [
        x
        for x in data
        if x["issue_id"] == issue_id
    ]
    return latest_coredumps

def download_coredump(coredump_id):
    params = {'format': 'elf'}
    r = requests.get(
        f"{base_url}/{org}/{proj}/coredumps/{coredump_id}/download", params=params,
        auth=(username, api_key), timeout=10
    )
    r.raise_for_status()
    return r.content

def get_metric_LteTimeToConnect(device_serial):
    r = requests.get(
        f"{base_url}/{org}/{proj}/devices/{device_serial}/attributes",
        auth=(username, api_key), timeout=10
    )
    r.raise_for_status()
    data = r.json()["data"]
    metrics = [
        x
        for x in data
        if x['custom_metric']['string_key'] == "Ncs_LteTimeToConnect"
    ]
    return metrics[0]
