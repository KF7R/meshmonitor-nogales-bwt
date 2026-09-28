# Arizona Border Wait Times for MeshMonitor

A compact MeshMonitor Auto-Responder that reports live Arizona land-port wait times from the public U.S. Customs and Border Protection Border Wait Times JSON feed.

No API key is required.

## Commands

- `/douglasborder`
- `/lukevilleborder`
- `/nacoborder`
- `/nogalesborder`
- `/sanluisborder`

A town command automatically summarizes every CBP crossing record for that town. For example, `/nogalesborder` includes DeConcini, Mariposa, and Morley Gate when those records are present in the CBP feed.

## What it reports

- 🟢 open / 🔴 closed status from CBP
- 🕒 published hours of operation
- 🚗 standard passenger-vehicle wait
- 🛃 SENTRI wait when available
- 🚶 pedestrian wait when available

Commercial traffic is intentionally omitted.

Closed ports show their status and hours instead of stale lane waits.

Example:

```
🛂 Nogales Border
🟢 Deconcini · 24 hrs/day · 🚗65m 🛃65m 🚶0m
🟢 Mariposa · 6 am-10 pm · 🚗40m 🚶0m
🔴 Morley Gate · CLOSED · 10 am-6 pm
```

## Data source

The script makes one request per invocation to the CBP JSON feed:

`https://bwt.cbp.gov/api/waittimes`

It then filters the returned records by Arizona town. There is no RSS, XML, or HTML parsing.

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
docker compose up -d
```

Test without transmitting over Meshtastic:

```bash
docker exec -e MESSAGE="/nogalesborder" meshmonitor python3 /data/scripts/border_wait.py
```

Expected output is MeshMonitor JSON containing either `response` or, when a town has enough crossing data to exceed the compact message budget, `responses`.

Configure the MeshMonitor Auto-Responder to invoke `border_wait.py` for the town commands above.

## Notes

- Uses CBP `port_status` for open/closed state; hours are displayed rather than used as the primary status calculation.
- Numeric `delay_minutes` is used when CBP supplies it, including cases where descriptive status text may say “no delay.”
- 8-second HTTP timeout.
- Replies target a 195-character budget; multi-crossing towns can be split into multiple responses rather than hard-truncated.
- No commercial lane data is transmitted.

## License

MIT.
