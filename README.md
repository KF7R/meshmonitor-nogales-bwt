# Arizona Border Wait Times for MeshMonitor

A compact MeshMonitor Auto-Responder that reports current Arizona land-port wait times from the public U.S. Customs and Border Protection (CBP) Border Wait Times JSON feed.

No API key is required.

## Commands

- `/douglasborder`
- `/lukevilleborder`
- `/nacoborder`
- `/nogalesborder`
- `/sanluisborder`

Each command summarizes the CBP crossing records for that Arizona border town. For example, `/nogalesborder` can include DeConcini, Mariposa, and Morley Gate.

## What it reports

- 🟢 / 🔴 CBP open or closed status
- Published hours of operation
- 🚗 standard passenger-vehicle wait
- `READY` Ready Lane wait when available
- `SENTRI` SENTRI wait when available
- 🚶 pedestrian wait when available

Commercial traffic is intentionally omitted.

Closed ports show `CLOSED` and their published hours instead of stale lane waits. Open CBP records with no usable Standard, Ready Lane, SENTRI, or pedestrian wait data are omitted.

Example:

```text
🟢 DeConcini · 24 hrs · 🚗105m SENTRI 60m 🚶0m
🔴 Mariposa · CLOSED · 6am-10pm
🔴 Morley Gate · CLOSED · 10am-6pm
```

Actual wait times and port status change throughout the day; the values above are only an output-format example.

## Data source

The script makes one request per invocation to the public CBP JSON feed:

`https://bwt.cbp.gov/api/waittimes`

It filters the returned records by Arizona border town. The current implementation does not parse the older CBP RSS/XML/HTML feeds.

## MeshMonitor setup

Bind-mount a scripts directory if you do not already have one:

```yaml
services:
  meshmonitor:
    volumes:
      - meshmonitor-data:/data
      - ./scripts:/data/scripts
```

Copy the script into the mounted directory and make it executable:

```bash
cp border_wait.py ~/meshmonitor/scripts/
chmod +x ~/meshmonitor/scripts/border_wait.py
```

Test from inside the MeshMonitor container without transmitting over Meshtastic:

```bash
docker exec -e MESSAGE="/nogalesborder" meshmonitor \
  python3 /data/scripts/border_wait.py
```

A normal result is JSON containing a `response` value. MeshMonitor's script **Run Test** screen can also be used to confirm the exact text that *would* be sent to the mesh without transmitting it.

Configure a MeshMonitor Auto Responder to invoke `border_wait.py` for the desired town commands.

## Behavior

- Uses CBP `port_status` for open/closed state rather than guessing from the current clock.
- Displays CBP's published hours in a compact format.
- Uses numeric `delay_minutes` when available.
- Shows only lane categories with usable current data.
- Suppresses open CBP records that contain no useful passenger or pedestrian wait data.
- Does not show stale lane waits when the overall port is closed.
- Uses an 8-second HTTP timeout.
- Targets a compact 195-character reply budget.
- Does not transmit commercial lane data.

## Requirements

- Python 3
- Network access from the MeshMonitor container to the CBP endpoint
- MeshMonitor with user-script / Auto Responder support

No third-party Python packages are required.

## License

MIT.
