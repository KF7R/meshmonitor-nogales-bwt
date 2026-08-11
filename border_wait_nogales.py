#!/usr/bin/env python3
# mm_meta:
# name: Nogales Border Wait Times
# emoji: 🛂
# language: Python

"""
Border crossing wait time script for MeshMonitor Auto Responder.
Reports live northbound General-lane wait times for the Nogales, AZ
ports of entry (DeConcini and Mariposa) using CBP's public Border Wait
Time RSS feed. No API key required.

Scope: Personal (passenger) vehicles and pedestrians at both ports.
DeConcini also reports SENTRI status when available.

Suggested trigger pattern: border, crossing

Environment variables available (per MeshMonitor's Auto Responder spec):
- MESSAGE: Full message text
- FROM_NODE: Sender node number
- PACKET_ID: Message packet ID
- TRIGGER: Matched trigger pattern
- PARAM_*: Extracted parameters from trigger (unused here)
"""

import json
import re
import sys
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET

# CBP port codes (Nogales, AZ)
DECONCINI_PORT = "260401"
MARIPOSA_PORT = "260402"

BASE_URL = "https://bwt.cbp.gov/api/bwtRss/rssbyportnum/HTML/{crossing_type}/{port_code}"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; MeshMonitor-BorderWaitScript/1.0)",
}

TIMEOUT_SECONDS = 8  # keep well under the 10s auto-responder script timeout


def fetch_description(crossing_type: str, port_code: str) -> str:
    """
    Fetch the CBP RSS feed and return the raw inner content of the first
    item's <description> element.

    Note: CBP's feed embeds literal (unescaped) HTML tags like <h4>, <b>,
    and <br/> inside <description>, making it structurally nested XML
    rather than plain text. That means ElementTree's .text attribute only
    returns the text before the first nested tag. To get the full content
    (including everything after the first <br/>), we extract it directly
    from the raw response text with regex instead of walking the parsed tree.
    """
    url = BASE_URL.format(crossing_type=crossing_type, port_code=port_code)
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as resp:
        raw = resp.read().decode("utf-8", errors="replace")

    # Validate the feed is well-formed XML (raises if CBP returns garbage/HTML error page)
    ET.fromstring(raw)

    item_match = re.search(r"<item>(.*?)</item>", raw, re.DOTALL)
    if not item_match:
        raise ValueError("No <item> found in feed")

    desc_match = re.search(r"<description>(.*?)</description>", item_match.group(1), re.DOTALL)
    if not desc_match:
        raise ValueError("No <description> found in feed item")

    return desc_match.group(1)


def parse_lane_blocks(description: str) -> dict:
    """
    Split the description into blocks keyed by vehicle type
    (e.g. 'Passenger Vehicles', 'Pedestrian', 'Commercial Vehicles').
    """
    parts = re.split(r"<h4>\s*<b>\s*(.*?)\s*</b>\s*</h4>", description)
    # parts[0] is preamble (Hours/Date), then alternating [type, block, type, block, ...]
    blocks = {}
    for i in range(1, len(parts) - 1, 2):
        vehicle_type = parts[i].strip()
        blocks[vehicle_type] = parts[i + 1]
    return blocks


def extract_lane_status(block: str, lane_label: str) -> str:
    """
    Extract a short status string for a given lane type (e.g. 'General' or
    'Sentri') from a vehicle-type block. Returns something like
    '12min 3 lanes', 'closed', or 'n/a'.
    """
    match = re.search(rf"{lane_label} Lanes:\s*(.*?)\s*(?:<br\s*/?>|$)", block, re.IGNORECASE | re.DOTALL)
    if not match:
        return "n/a"
    text = match.group(1).strip()

    if not text or text.upper() == "N/A":
        return "n/a"
    if "closed" in text.lower() or "update pending" in text.lower():
        return "closed"

    delay_match = re.search(r"(no delay|(\d+)\s*min delay)", text, re.IGNORECASE)

    if delay_match:
        return "0m" if "no delay" in delay_match.group(1).lower() else f"{delay_match.group(2)}m"
    return "?"


def get_lane_wait(port_code: str, crossing_type: str, vehicle_key: str, lane_label: str = "General") -> str:
    """Fetch and extract a specific lane type's wait for one port/crossing-type combo."""
    try:
        description = fetch_description(crossing_type, port_code)
        blocks = parse_lane_blocks(description)
        block = blocks.get(vehicle_key)
        if block is None:
            return "n/a"
        return extract_lane_status(block, lane_label)
    except Exception as e:
        print(f"Error fetching {lane_label} {crossing_type} for port {port_code}: {e}", file=sys.stderr)
        return "n/a"


def get_border_report() -> str:
    deconcini_pov = get_lane_wait(DECONCINI_PORT, "POV", "Passenger Vehicles", "General")
    deconcini_sentri = get_lane_wait(DECONCINI_PORT, "POV", "Passenger Vehicles", "Sentri")
    deconcini_ped = get_lane_wait(DECONCINI_PORT, "PED", "Pedestrian", "General")
    mariposa_pov = get_lane_wait(MARIPOSA_PORT, "POV", "Passenger Vehicles", "General")
    mariposa_ped = get_lane_wait(MARIPOSA_PORT, "PED", "Pedestrian", "General")

    deconcini_parts = [f"PV {deconcini_pov}"]
    if deconcini_sentri != "n/a":
        deconcini_parts.append(f"SENTRI {deconcini_sentri}")
    deconcini_parts.append(f"PED {deconcini_ped}")

    mariposa_parts = [f"PV {mariposa_pov}"]
    if mariposa_ped != "n/a":
        mariposa_parts.append(f"PED {mariposa_ped}")

    return (
        f"DeConcini: {', '.join(deconcini_parts)} | "
        f"Mariposa: {', '.join(mariposa_parts)}"
    )


def main():
    try:
        message = get_border_report()
        # Meshtastic messages are short-range; keep well under 200 chars
        if len(message) > 195:
            message = message[:192] + "..."
        print(json.dumps({"response": message}))
    except urllib.error.URLError as e:
        print(f"Error: network/API failure: {e}", file=sys.stderr)
        print(json.dumps({"response": "Border wait times unavailable right now."}))
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        print(json.dumps({"response": "Sorry, border wait lookup failed."}))


if __name__ == "__main__":
    main()
