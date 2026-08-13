# Border Wait Times — MeshMonitor Auto-Responder Script

Reports live wait times for U.S. land ports of entry (Mexico and Canada
borders) using [CBP's public Border Wait Time RSS feed](https://bwt.cbp.gov).
No API key required.

Built for [MeshMonitor](https://github.com/Yeraze/meshmonitor)'s
[Auto Responder](https://meshmonitor.org/features/automation.html) feature.

Originally written for the Nogales, AZ ports of entry (DeConcini and
Mariposa); the script is now config-driven so any number of Mexico or
Canada crossings can be registered without touching the parsing logic.

## What it reports

By default, the ports listed in `DEFAULT_PORTS` (Nogales' DeConcini and
Mariposa out of the box):

- **DeConcini**: Passenger Vehicles (General lane), SENTRI (when available), Pedestrian
- **Mariposa**: Passenger Vehicles (General lane), Pedestrian

When a port is closed, or CBP shows "Update Pending" (e.g. outside a
port's staffed hours), the script reports `closed` rather than a stale
number.

**Example output (default ports):**

```
DeConcini: Cars 10m, SENTRI closed, Pedestrians 0m | Mariposa: Cars closed, Pedestrians closed
```

**Example output (querying a specific registered port):**

```
/border mariposa
Mariposa: Cars closed, Pedestrians closed
```

- `Cars` = Passenger Vehicles
- `Pedestrians` = Pedestrian
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

   ```
   cp border_wait.py ~/meshmonitor/scripts/
   chmod +x ~/meshmonitor/scripts/border_wait.py
   docker compose up -d
   ```

3. Test it directly inside the container:

   ```
   docker exec meshmonitor python3 /data/scripts/border_wait.py
   ```

   To test a specific port lookup, set `MESSAGE` first:

   ```
   docker exec -e MESSAGE="border mariposa" meshmonitor python3 /data/scripts/border_wait.py
   ```

4. In the MeshMonitor UI: **Dashboard → Sources → Edit Source → Auto-Responder**
   (configured per-source in MeshMonitor 4.0+), add a trigger:

   - **Trigger pattern:** `border, crossing, line, garita`
   - **Script:** `border_wait.py`

5. Send `/border` on the mesh for the default ports, or `/border <alias>`
   (e.g. `/border mariposa`, `/border blaine`) for a specific registered
   crossing — see **Registering ports** below for aliases.

## Registering ports (Mexico and Canada crossings)

All configuration lives in the `PORTS` dict near the top of the script.
Each entry looks like this:

```python
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
```

To add a new crossing:

1. **Find the port code.** Go to [bwt.cbp.gov](https://bwt.cbp.gov), open the
   crossing's detail page, and read the code out of the URL — e.g.
   `/details/08260401/POV` → port code `260401`.

2. **Add a dict entry** with a short internal key (e.g. `"peace_arch"`), a
   display `name`, the `port_code`, one or more lowercase `aliases`
   users can type to query it directly, and a `lanes` list.

3. **Decide which lanes to report.** Each lane tuple is
   `(crossing_type, vehicle_key, lane_label, short_tag)`:
   - `crossing_type` — CBP feed type: `"POV"` (personal vehicle), `"PED"`
     (pedestrian), or `"COV"` (commercial vehicle).
   - `vehicle_key` — the block heading in the feed, typically
     `"Passenger Vehicles"`, `"Pedestrian"`, or `"Commercial Vehicles"`.
   - `lane_label` — the specific lane field inside that block: commonly
     `"General"`, `"Sentri"`, `"Ready"`, or `"Nexus"`.
   - `short_tag` — what appears in the mesh reply, e.g. `"Cars"`, `"NEXUS"`.

4. **Verify the lane label before trusting it.** CBP's feed schema isn't
   perfectly uniform across all 328 ports. Northern (Canada) crossings use
   NEXUS instead of SENTRI for trusted travelers, some pedestrian crossings
   expose a `"Ready"` lane, and label text can otherwise vary port to port.
   After adding a port, run the script (Setup step 3) and check the
   output — if a lane always comes back `n/a`, the label text is probably
   wrong. Open that port's raw feed URL directly in a browser to see the
   exact text CBP uses:

   ```
   https://bwt.cbp.gov/api/bwtRss/rssbyportnum/HTML/POV/<port_code>
   ```

5. **Add it to `DEFAULT_PORTS`** if you want it included in the plain
   `/border` reply with no port name — or leave it out and let people
   query it by alias, e.g. `/border blaine`.

### A note on scaling to many crossings

Meshtastic messages are short-range and the auto-responder keeps replies
well under 200 characters. Every port in `DEFAULT_PORTS` adds to *every*
default reply, so:

- Keep `DEFAULT_PORTS` to the one or two crossings your community actually
  cares about by default (e.g. the nearest one).
- Register additional crossings without adding them to `DEFAULT_PORTS`,
  and let people pull them up by name (`/border <alias>`) instead. This
  keeps replies short and lets one deployment cover a whole region (e.g.
  all the crossings along a stretch of the Mexico or Canada border) without
  every reply trying to report on all of them at once.
- If a single port's own lane list runs long (e.g. General + Sentri/Nexus
  + Ready + Commercial), consider trimming `lanes` to the ones your users
  actually ask about rather than relying on the script's truncation, which
  is a blunt last resort and can cut off a reply mid-word.

## Notes

- 8-second HTTP timeout, well under MeshMonitor's 10-second script execution limit.
- Fails gracefully — if CBP's feed is unreachable, it returns a short
  "unavailable" message instead of crashing, and logs the actual error to
  stderr (`docker logs meshmonitor`).
- Each port's feed is fetched at most once per run (cached in-process),
  even if multiple lanes are requested from it.

## License

MIT — do whatever you want with this, no warranty.
