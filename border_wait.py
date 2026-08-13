#!/usr/bin/env python3
# mm_meta:
# name: Border Wait Times
# emoji: 🛂
# language: Python
"""
Border crossing wait time script for MeshMonitor Auto Responder.

Reports live wait times for one or more U.S. land ports of entry (Mexico
or Canada border) using CBP's public Border Wait Time RSS feed. No API
key required.

This is a multi-port generalization of the original Nogales-only script.
Add new crossings to the PORTS dict below -- no other code changes are
needed for the common case.

Suggested trigger pattern: border, crossing, line, garita

Environment variables available (per MeshMonitor's Auto Responder spec):
- MESSAGE: Full message text
- FROM_NODE: Sender node number
- PACKET_ID: Message packet ID
- TRIGGER: Matched trigger pattern
- PARAM_*: Extracted parameters from trigger

Optional query: if the message includes a recognized port name/alias
after the trigger word (e.g. "/border mariposa" or "/border blaine"),
only that port is reported. Otherwise DEFAULT_PORTS is reported.
"""

import json
import os
import re
import sys
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET

BASE_URL = "https://bwt.cbp.gov/api/bwtRss/rssbyportnum/HTML/{crossing_type}/{port_code}"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; MeshMonitor-BorderWaitScript/2.0)"}
TIMEOUT_SECONDS = 8  # keep well under the 10s auto-responder script timeout
MAX_REPLY_CHARS = 195  # Meshtastic messages are short-range; keep well under 200 chars

# ---------------------------------------------------------------------------
# PORT CONFIGURATION
#
# Add a crossing by adding a key to PORTS. Find CBP port codes at
# bwt.cbp.gov -- open a port's detail page and the code is in the URL
# (e.g. /details/08260401/POV -> port code 260401).
#
# Each lane tuple is: (crossing_type, vehicle_key, lane_label, short_tag)
#   crossing_type: CBP feed type -- "POV" (personal vehicle), "PED"
#                  (pedestrian), or "COV" (commercial vehicle)
#   vehicle_key:   the <h4><b> block heading in the feed, e.g.
#                  "Passenger Vehicles", "Pedestrian", "Commercial Vehicles"
#   lane_label:    the "<lane_label> Lanes:" field inside that block --
#                  commonly "General", "Sentri", "Ready", or "Nexus".
#                  IMPORTANT: label text can vary port to port, and CBP's
#                  feed doesn't consistently distinguish SENTRI vs NEXUS in
#                  the underlying field name even at northern crossings.
#                  Before adding a new port, run the script (see Setup
#                  step 3 in the README) and check the output -- if a lane
#                  always comes back "n/a", open that port's raw feed
#                  (BASE_URL above, filled in by hand) and confirm the
#                  exact label CBP uses for that lane at that port.
#   short_tag:     what shows up in the mesh message, e.g. "PV", "SENTRI"
#
# aliases: lowercase words a user can type after the trigger to query just
#          this port, e.g. "/border mariposa". Matching is a case-
#          insensitive substring match against the incoming message.
# ---------------------------------------------------------------------------

PORTS = {
    "deconcini": {
        "name": "DeConcini",
        "port_code": "260401",
        "aliases": ["deconcini"],
        "lanes": [
            ("POV", "Passenger Vehicles", "General", "Cars"),
            ("POV", "Passenger Vehicles", "Sentri", "SENTRI"),
            ("PED", "Pedestrian", "General", "Pedestrians"),
        ],
    },
    "mariposa": {
        "name": "Mariposa",
        "port_code": "260402",
        "aliases": ["mariposa"],
        "lanes": [
            ("POV", "Passenger Vehicles", "General", "Cars"),
            ("PED", "Pedestrian", "General", "Pedestrians"),
        ],
    },

    # --- Example additional crossings ------------------------------------
    # Port codes below are placeholders -- verify every one at bwt.cbp.gov
    # before relying on it. Uncomment and edit as needed; each entry is
    # independent, so you can register as many as you want.
    #
    # "san_ysidro": {
    #     "name": "San Ysidro",
    #     "port_code": "250401",  # VERIFY at bwt.cbp.gov
    #     "aliases": ["sanysidro", "tijuana"],
    #     "lanes": [
    #         ("POV", "Passenger Vehicles", "General", "Cars"),
    #         ("POV", "Passenger Vehicles", "Sentri", "SENTRI"),
    #         ("PED", "Pedestrian", "General", "Pedestrians"),
    #         ("PED", "Pedestrian", "Ready", "READY"),
    #     ],
    # },
    # "peace_arch": {
    #     "name": "Peace Arch",
    #     "port_code": "3004",  # Blaine, WA -- Canada border
    #     "aliases": ["peacearch", "blaine"],
    #     "lanes": [
    #         ("POV", "Passenger Vehicles", "General", "Cars"),
    #         ("POV", "Passenger Vehicles", "Nexus", "NEXUS"),
    #     ],
    # },
}

# Ports reported when the message doesn't name a specific port.
# Keep this short -- every port added here adds to every default reply.
DEFAULT_PORTS = ["deconcini", "mariposa"]


def fetch_description(crossing_type: str, port_code: str) -> str:
    """
    Fetch the CBP RSS feed and return the raw inner content of the first
    item's <description> element.

    Note: CBP's feed embeds literal (unescaped) HTML tags like <h4>, <b>,
    and <br/> inside <description>, making it structurally nested XML
    rather than plain text. That means ElementTree's .text attribute only
    returns the text before the first nested tag. To get the full content
    (including everything after the first <br/>), we extract it directly
    from the raw response text with regex instead of walking the parsed
    tree.
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
    Extract a short status string for a given lane type (e.g. 'General',
    'Sentri', 'Nexus', or 'Ready') from a vehicle-type block. Returns
    something like '12min 3 lanes', 'closed', or 'n/a'.
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


# Per-run cache so a port's feed is fetched at most once even if it has
# several lanes to look up. Keyed by (crossing_type, port_code).
_description_cache = {}


def get_lane_wait(port_code: str, crossing_type: str, vehicle_key: str, lane_label: str) -> str:
    """Fetch (with caching) and extract a specific lane's wait for one port/crossing-type combo."""
    cache_key = (crossing_type, port_code)
    try:
        if cache_key not in _description_cache:
            _description_cache[cache_key] = fetch_description(crossing_type, port_code)
        description = _description_cache[cache_key]
        blocks = parse_lane_blocks(description)
        block = blocks.get(vehicle_key)
        if block is None:
            return "n/a"
        return extract_lane_status(block, lane_label)
    except Exception as e:
        print(f"Error fetching {lane_label} {crossing_type} for port {port_code}: {e}", file=sys.stderr)
        return "n/a"


def build_port_report(port_key: str) -> str:
    """Build a 'Name: PV Xm, SENTRI Ym, PED Zm' string for one configured port."""
    port = PORTS[port_key]
    parts = []
    for crossing_type, vehicle_key, lane_label, short_tag in port["lanes"]:
        status = get_lane_wait(port["port_code"], crossing_type, vehicle_key, lane_label)
        if status == "n/a":
            continue
        parts.append(f"{short_tag} {status}")
    if not parts:
        return f"{port['name']}: unavailable"
    return f"{port['name']}: {', '.join(parts)}"


def match_requested_ports(text: str) -> list:
    """
    Look for a configured port alias inside free text (e.g. the trigger
    param or the raw message '/border mariposa'). Returns matched port
    keys in PORTS dict order, or [] if none matched.
    """
    if not text:
        return []
    lowered = text.lower()
    return [key for key, port in PORTS.items() if any(alias in lowered for alias in port["aliases"])]


def get_border_report() -> str:
    # MeshMonitor's Auto Responder exposes named trigger captures as
    # PARAM_* env vars. Fall back to scanning the raw MESSAGE text so this
    # still works even with a plain (non-capturing) trigger pattern.
    param_hint = " ".join(v for k, v in os.environ.items() if k.startswith("PARAM_") and v)
    message = os.environ.get("MESSAGE", "")
    requested = match_requested_ports(param_hint) or match_requested_ports(message)

    port_keys = requested if requested else DEFAULT_PORTS
    port_keys = [k for k in port_keys if k in PORTS]
    if not port_keys:
        return "Unknown port of entry. Try: " + ", ".join(sorted(p["aliases"][0] for p in PORTS.values()))

    reports = [build_port_report(k) for k in port_keys]
    message_out = " | ".join(reports)

    # Dropping specific lanes to fit a length budget is very config-
    # dependent, so this only does a last-resort hard truncate. If you
    # register many ports under DEFAULT_PORTS, prefer querying them by
    # name instead of relying on this to fit everything in one message.
    if len(message_out) > MAX_REPLY_CHARS:
        message_out = message_out[: MAX_REPLY_CHARS - 3] + "..."
    return message_out


def main():
    try:
        message = get_border_report()
        print(json.dumps({"response": message}))
    except urllib.error.URLError as e:
        print(f"Error: network/API failure: {e}", file=sys.stderr)
        print(json.dumps({"response": "Border wait times unavailable right now."}))
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        print(json.dumps({"response": "Sorry, border wait lookup failed."}))


if __name__ == "__main__":
    main()
