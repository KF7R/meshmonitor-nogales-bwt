#!/usr/bin/env python3
# mm_meta:
# name: US Border Wait Times
# emoji: 🛂
# language: Python
"""MeshMonitor auto-responder for CBP U.S. land-border wait times."""

import json
import os
import re
import sys
import urllib.error
import urllib.request

API_URL = "https://bwt.cbp.gov/api/waittimes"
HEADERS = {"User-Agent": "MeshMonitor-US-BorderWait/4.0"}
TIMEOUT = 8
MAX_REPLY_CHARS = 195

# Friendly command aliases for CBP port names that are awkward or commonly
# known by another city name. All other CBP port names resolve dynamically.
ALIASES = {
    "buffalo": "buffaloniagarafalls",
    "niagara": "buffaloniagarafalls",
    "niagarafalls": "buffaloniagarafalls",
    "sandiego": "sanysidro",
}

def normalize(value):
    return re.sub(r"[^a-z0-9]", "", str(value).lower())

def fetch_ports():
    req = urllib.request.Request(API_URL, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return json.load(resp)

def requested_command():
    text = " ".join(
        [os.environ.get("MESSAGE", ""), os.environ.get("TRIGGER", "")]
        + [v for k, v in os.environ.items() if k.startswith("PARAM_")]
    ).lower()
    match = re.search(r"/?([a-z0-9]+)border\b", text)
    return match.group(1) if match else None

def resolve_ports(data, command):
    wanted = ALIASES.get(command, command)
    border_ports = [
        p for p in data
        if p.get("border") in ("Mexican Border", "Canadian Border")
    ]

    exact = [
        p for p in border_ports
        if normalize(p.get("port_name", "")) == wanted
    ]
    if exact:
        return exact

    prefix = [
        p for p in border_ports
        if normalize(p.get("port_name", "")).startswith(wanted)
    ]
    port_names = {normalize(p.get("port_name", "")) for p in prefix}
    return prefix if len(port_names) == 1 else []
def lane_wait(lane):
    if not lane:
        return None
    status = str(lane.get("operational_status", "")).lower()
    if "closed" in status:
        return None
    delay = str(lane.get("delay_minutes", "")).strip()
    if delay.isdigit():
        return f"{int(delay)}m"
    if "no delay" in status:
        return "0m"
    return None

def clean_hours(value):
    hours = (value or "hours n/a").strip()
    hours = hours.replace("24 hrs/day", "24 hrs")
    hours = re.sub(r"\s+(am|pm)", r"\1", hours, flags=re.I)
    return hours

def display_name(port):
    name = (port.get("crossing_name") or port.get("port_name") or "POE").strip()
    if name.lower() == "deconcini":
        return "DeConcini"
    return name

def crossing_line(port):
    name = display_name(port)
    hours = clean_hours(port.get("hours"))
    is_open = str(port.get("port_status", "")).lower() == "open"

    if not is_open:
        return f"🔴 {name} · CLOSED · {hours}"

    passenger = port.get("passenger_vehicle_lanes") or {}
    pedestrian = port.get("pedestrian_lanes") or {}

    standard = lane_wait(passenger.get("standard_lanes"))
    ready = lane_wait(passenger.get("ready_lanes"))
    trusted = lane_wait(passenger.get("NEXUS_SENTRI_lanes"))
    ped = lane_wait(pedestrian.get("standard_lanes"))

    parts = []
    if standard:
        parts.append(f"🚗{standard}")
    if ready:
        parts.append(f"READY {ready}")
    if trusted:
        label = "NEXUS" if port.get("border") == "Canadian Border" else "SENTRI"
        parts.append(f"{label} {trusted}")
    if ped:
        parts.append(f"🚶{ped}")

    if not parts:
        return None

    return f"🟢 {name} · {hours} · {' '.join(parts)}"

def build_report(data, command):
    matches = resolve_ports(data, command)
    if not matches:
        return f"🛂 /{command}border: CBP port not found."

    lines = [line for p in matches if (line := crossing_line(p))]
    if not lines:
        return f"🛂 /{command}border: waits unavailable."

    message = "\n".join(lines)
    if len(message) <= MAX_REPLY_CHARS:
        return message
    return lines

def main():
    command = requested_command()
    if not command:
        print(json.dumps({
            "response": "🛂 Use /<port>border, e.g. /nogalesborder or /detroitborder"
        }, ensure_ascii=False))
        return

    try:
        data = fetch_ports()
        report = build_report(data, command)
        key = "responses" if isinstance(report, list) else "response"
        print(json.dumps({key: report}, ensure_ascii=False))
    except (urllib.error.URLError, TimeoutError, ValueError) as e:
        print(f"CBP lookup failed: {e}", file=sys.stderr)
        print(json.dumps({
            "response": "🛂 Border wait times unavailable right now."
        }, ensure_ascii=False))

if __name__ == "__main__":
    main()
