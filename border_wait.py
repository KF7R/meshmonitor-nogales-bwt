#!/usr/bin/env python3
# mm_meta:
# name: Arizona Border Wait Times
# emoji: 🛂
# language: Python
"""MeshMonitor auto-responder for Arizona CBP border wait times."""

import json
import os
import re
import sys
import urllib.error
import urllib.request

API_URL = "https://bwt.cbp.gov/api/waittimes"
HEADERS = {"User-Agent": "MeshMonitor-AZ-BorderWait/3.0"}
TIMEOUT = 8
MAX_REPLY_CHARS = 195

ARIZONA_TOWNS = {
    "douglas": "douglas",
    "lukeville": "lukeville",
    "naco": "naco",
    "nogales": "nogales",
    "sanluis": "san luis",
}

def fetch_ports():
    req = urllib.request.Request(API_URL, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return json.load(resp)

def requested_town():
    text = " ".join(
        [os.environ.get("MESSAGE", ""), os.environ.get("TRIGGER", "")]
        + [v for k, v in os.environ.items() if k.startswith("PARAM_")]
    ).lower()
    compact = re.sub(r"[^a-z]", "", text)
    for command, cbp_name in ARIZONA_TOWNS.items():
        if f"{command}border" in compact or command in compact:
            return command, cbp_name
    return None, None

def lane_wait(lane):
    if not lane:
        return None
    delay = str(lane.get("delay_minutes", "")).strip()
    status = str(lane.get("operational_status", "")).lower()
    if delay.isdigit():
        return f"{int(delay)}m"
    if "closed" in status:
        return "closed"
    return None

def crossing_line(port):
    name = (port.get("crossing_name") or port.get("port_name") or "POE").strip()
    if name.lower() == "deconcini":
        name = "DeConcini"

    hours = (port.get("hours") or "hours n/a").strip()
    hours = hours.replace("24 hrs/day", "24 hrs")
    hours = re.sub(r"\s+(am|pm)", r"\1", hours, flags=re.I)

    is_open = str(port.get("port_status", "")).lower() == "open"
    status = "🟢" if is_open else "🔴"
    if not is_open:
        return f"{status} {name} · CLOSED · {hours}"

    passenger = port.get("passenger_vehicle_lanes") or {}
    pedestrian = port.get("pedestrian_lanes") or {}
    parts = []

    standard = lane_wait(passenger.get("standard_lanes"))
    ready = lane_wait(passenger.get("ready_lanes"))
    sentri = lane_wait(passenger.get("NEXUS_SENTRI_lanes"))
    ped = lane_wait(pedestrian.get("standard_lanes"))

    if standard and standard != "closed":
        parts.append(f"🚗{standard}")
    if ready and ready != "closed":
        parts.append(f"READY {ready}")
    if sentri and sentri != "closed":
        parts.append(f"SENTRI {sentri}")
    if ped and ped != "closed":
        parts.append(f"🚶{ped}")

    if not parts:
        return None

    return f"{status} {name} · {hours} · {' '.join(parts)}"

def build_report(data, command, cbp_name):
    matches = [
        p for p in data
        if cbp_name in str(p.get("port_name", "")).lower()
        and p.get("border") == "Mexican Border"
    ]
    if not matches:
        return f"🛂 {command.title()} Border: CBP data unavailable."

    lines = [line for p in matches if (line := crossing_line(p))]
    if not lines:
        return f"🛂 {command.title()} Border: waits unavailable."

    message = "\n".join(lines)
    if len(message) <= MAX_REPLY_CHARS:
        return message
    return lines

def main():
    command, cbp_name = requested_town()
    if not command:
        cmds = " ".join(f"/{x}border" for x in ARIZONA_TOWNS)
        print(json.dumps({"response": f"🛂 AZ border commands: {cmds}"}, ensure_ascii=False))
        return
    try:
        report = build_report(fetch_ports(), command, cbp_name)
        key = "responses" if isinstance(report, list) else "response"
        print(json.dumps({key: report}, ensure_ascii=False))
    except (urllib.error.URLError, TimeoutError, ValueError) as e:
        print(f"CBP lookup failed: {e}", file=sys.stderr)
        print(json.dumps({"response": "🛂 Border wait times unavailable right now."}, ensure_ascii=False))

if __name__ == "__main__":
    main()
