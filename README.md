# Nogales Border Wait Times — MeshMonitor Auto-Responder Script

Reports live northbound wait times for the Nogales, AZ ports of entry — **DeConcini** and
**Mariposa** — using [CBP's public Border Wait Time RSS feed](https://bwt.cbp.gov). No API key
required.

Built for [MeshMonitor](https://github.com/Yeraze/meshmonitor)'s
[Auto Responder](https://meshmonitor.org/features/automation.html) feature.

## What it reports

- **DeConcini**: Passenger Vehicles (General lane), SENTRI (when available), Pedestrian
- **Mariposa**: Passenger Vehicles (General lane), Pedestrian

When a port is closed, or CBP shows "Update Pending" (e.g. Mariposa outside its 6am–10pm hours),
the script reports `closed` rather than a stale number.

**Example output:**
```
DeConcini: PV 10m, SENTRI closed, PED 0m | Mariposa: PV closed, PED closed
```

- `PV` = Passenger Vehicles
- `PED` = Pedestrian
- Numbers are minutes of estimated delay

## Setup

1. Bind-mount a local `scripts/` folder into your MeshMonitor container (`docker-compose.yml`):

   ```yaml
   services:
     meshmonitor:
       volumes:
         - meshmonitor-data:/data
         - ./scripts:/data/scripts
   ```

2. Copy this script into that folder and make it executable:

   ```bash
   cp border_wait_nogales.py ~/meshmonitor/scripts/
   chmod +x ~/meshmonitor/scripts/border_wait_nogales.py
   docker compose up -d
   ```

3. Test it directly inside the container:

   ```bash
   docker exec meshmonitor python3 /data/scripts/border_wait_nogales.py
   ```

4. In the MeshMonitor UI: **Dashboard → Sources → Edit Source → Auto-Responder** (configured
   per-source in MeshMonitor 4.0+), add a trigger:

   - **Trigger pattern:** `border, crossing, line, garita`
   - **Script:** `border_wait_nogales.py`

5. Send `/border` or `/bwt` on the mesh to test.

## Adapting for another port of entry

The `DECONCINI_PORT` and `MARIPOSA_PORT` constants near the top of the script are CBP port codes.
Find codes for other crossings at [bwt.cbp.gov](https://bwt.cbp.gov) — open a port's detail page
and the code is in the URL (e.g. `/details/08260401/POV` → port code `260401`).

## Notes

- 8-second HTTP timeout, well under MeshMonitor's 10-second script execution limit.
- Fails gracefully — if CBP's feed is unreachable, it returns a short "unavailable" message
  instead of crashing, and logs the actual error to stderr (`docker logs meshmonitor`).

## License

MIT — do whatever you want with this, no warranty.
