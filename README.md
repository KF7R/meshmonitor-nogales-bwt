# U.S. Land Border Wait Times for MeshMonitor

A compact MeshMonitor Auto-Responder that reports current passenger and pedestrian wait times for U.S. land ports of entry on both the Mexican and Canadian borders using the public U.S. Customs and Border Protection (CBP) Border Wait Times JSON feed.

No API key is required.

## Commands

Commands use the form `/<port>border`. The responder resolves CBP port names dynamically and includes friendly aliases for commonly used city names.

### Mexican border

- `/andradeborder`
- `/brownsvilleborder`
- `/calexicoborder`
- `/columbusborder`
- `/delrioborder`
- `/douglasborder`
- `/eaglepassborder`
- `/elpasoborder`
- `/forthancockborder`
- `/hidalgopharrborder`
- `/laredoborder`
- `/lukevilleborder`
- `/nacoborder`
- `/nogalesborder`
- `/otaymesaborder`
- `/presidioborder`
- `/progresoborder`
- `/riograndecityborder`
- `/romaborder`
- `/sanluisborder`
- `/sanysidroborder` (alias: `/sandiegoborder`)
- `/santateresaborder`
- `/tecateborder`

### Canadian border

- `/alexandriabayborder`
- `/blaineborder`
- `/buffaloborder` (Buffalo/Niagara Falls)
- `/calaisborder`
- `/champlainborder`
- `/derbylineborder`
- `/detroitborder`
- `/highgatespringsborder`
- `/houltonborder`
- `/internationalfallsborder`
- `/jackmanborder`
- `/lyndenborder`
- `/madawaskaborder`
- `/massenaborder`
- `/nortonborder`
- `/ogdensburgborder`
- `/pembinaborder`
- `/porthuronborder`
- `/saultstemarieborder`
- `/sumasborder`
- `/sweetgrassborder`

CBP may group several crossings under one port. For example, `/nogalesborder` can include DeConcini, Mariposa and Morley Gate; `/detroitborder` can include Ambassador Bridge, Gordie Howe International Bridge and Windsor Tunnel; and `/blaineborder` can include Pacific Highway, Peace Arch and Point Roberts.

## What it reports

- 🟢 / 🔴 CBP open or closed status
- Published hours of operation
- 🚗 standard passenger-vehicle wait
- `READY` Ready Lane wait when available
- `SENTRI` on the Mexican border
- `NEXUS` on the Canadian border
- 🚶 pedestrian wait when available

Commercial traffic is intentionally omitted.

Closed ports show `CLOSED` and their published hours instead of stale lane waits. Open CBP records with no usable Standard, Ready Lane, SENTRI/NEXUS, or pedestrian wait data are omitted. Records whose lane data is only `Update Pending` therefore do not report a false zero-minute wait.

Example:

```text
🟢 DeConcini · 24 hrs · 🚗90m SENTRI 60m 🚶5m
🔴 Mariposa · CLOSED · 6am-10pm
```

Canadian example:

```text
🟢 Pacific Highway · 24 hrs · 🚗5m NEXUS 0m
🟢 Peace Arch · 24 hrs · 🚗20m NEXUS 0m
```

Actual wait times and port status change throughout the day; these values are output-format examples only.

## Data source

The script makes one request per invocation to the public CBP JSON feed:

`https://bwt.cbp.gov/api/waittimes`

It filters the national dataset to the requested Mexican- or Canadian-border port. The current implementation does not parse the older CBP RSS/XML/HTML feeds.

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

MeshMonitor's script **Run Test** screen can confirm the exact text that would be sent without transmitting it. A short result uses a JSON `response` value. If a multi-crossing report exceeds the reply budget, the script returns a `responses` array; MeshMonitor sends those entries as separate messages.

Configure a MeshMonitor Auto Responder to invoke `border_wait.py` for the desired commands.

## Behavior

- Uses CBP `port_status` for open/closed state rather than guessing from the current clock.
- Displays CBP's published hours in a compact format.
- Uses numeric `delay_minutes` when available.
- Treats an explicitly closed lane as unavailable even if stale numeric data exists.
- Shows only lane categories with usable current data.
- Labels the trusted-traveler lane `SENTRI` for Mexico and `NEXUS` for Canada.
- Suppresses open CBP records that contain no useful passenger or pedestrian wait data.
- Does not show stale lane waits when the overall port is closed.
- Uses an 8-second HTTP timeout.
- Targets a compact 195-character reply budget before using multiple MeshMonitor responses.
- Does not transmit commercial lane data.

## Requirements

- Python 3
- Network access from the MeshMonitor container to the CBP endpoint
- MeshMonitor with user-script / Auto Responder support

No third-party Python packages are required.

## License

MIT.
