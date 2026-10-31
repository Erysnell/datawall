# datawall — Network data usage tracker per program

> **Español:** También disponible en [español](README.es.md).

Release notes live in [CHANGELOG.md](CHANGELOG.md).

Per-process network traffic monitor for Linux. Displays each program's
daily sent/received data in a formatted terminal table with visual bars
and current transfer speed.

```
╭─────────────────────────── DataWall — 2026-07-13 ────────────────────────────╮
│                                                                              │
│  ┏━━━━━━━━━━━━━━┳━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━┓        │
│  ┃ Program      ┃    Sent ┃ Received ┃    Total ┃ %                 ┃        │
│  ┣━━━━━━━━━━━━━━╋━━━━━━━━━╋━━━━━━━━━━╋━━━━━━━━━━╋━━━━━━━━━━━━━━━━━━━┫        │
│  ┃ firefox      ┃ 15.2 MB ┃  82.1 MB ┃  97.3 MB ┃ ██████░░░░  62.3% ┃        │
│  ┃ unattributed ┃  8.7 MB ┃  35.3 MB ┃  44.0 MB ┃ ██░░░░░░░░  28.2% ┃        │
│  ┃ discord      ┃  2.1 MB ┃  12.8 MB ┃  14.9 MB ┃ █░░░░░░░░░   9.5% ┃        │
│  ┃ TOTAL        ┃ 26.0 MB ┃ 130.2 MB ┃ 156.2 MB ┃                   ┃        │
│  ┗━━━━━━━━━━━━━━┻━━━━━━━━━┻━━━━━━━━━━┻━━━━━━━━━━┻━━━━━━━━━━━━━━━━━━━┛        │
│                                                                              │
╰────────────────── Speed:  ↑ 1.2 MB/s  ↓ 3.8 MB/s   [wlo1] ───────────────────╯
  'unattributed' is 28% — run datawall explain for the breakdown
  Daemon: running
```

## Requirements

| Package | Purpose |
|---|---|
| `python3` | Runtime |
| `python3-psutil` | Kernel network counter reader |
| `python3-rich` | Terminal tables and bars |
| `iproute2` | `ss` command for exact per-socket data (preinstalled on every Linux) |

## Installation

### From .deb

```bash
sudo apt install ./datawall_1.1.0_all.deb
```

Or with dpkg (dependencies must be resolved manually):

```bash
sudo dpkg -i datawall_1.1.0_all.deb
sudo apt install -f
```

### Manual

```bash
pip install psutil rich
chmod +x datawall
ln -sf "$PWD/datawall" ~/.local/bin/datawall
```

## Usage

| Command | Description |
|---|---|
| `datawall` | Show daily report |
| `datawall start` | Start background daemon |
| `datawall stop` | Stop background daemon |
| `datawall restart` | Restart daemon |
| `datawall status` | Check if daemon is running |
| `datawall reset` | Reset today's accumulated data |
| `datawall watch` | Real-time bandwidth monitor (top/htop-like) |
| `datawall days N` | Aggregated report for last N days |
| `datawall limit` | Show daily limit and current usage |
| `datawall limit SIZE` | Set daily limit (e.g. 5GB, 500MB) |
| `datawall limit off` | Remove daily limit |
| `datawall connections` | Show active TCP connections per remote address |
| `datawall explain` | Diagnose where `unattributed` traffic comes from |
| `datawall explain N` | Same, sampling for N seconds (default 4) |
| `datawall --version` | Print the version |

## Auto-start with systemd

```bash
systemctl --user enable --now datawall.service
```

## How it works

### 1. Sampling daemon

The daemon runs in the background and every 5 seconds:

1. Reads total network counters from the kernel (`psutil.net_io_counters`)
2. Snapshots all open TCP sockets with their exact byte counters
3. Compares against the previous snapshot to compute per-socket deltas
4. Accumulates those deltas by process name in `~/.datawall/store.json`

### 2. Per-process tracking (SOCK_DIAG)

Uses `ss -tpin` to read exact per-socket counters from the kernel via
netlink: `bytes_acked` (sent) and `bytes_received`.

Each socket is identified by `(pid, fd)`. The daemon caches the last
seen value and computes the delta on the next sample.

If `ss` is not available, it falls back to proportional attribution
by connection count.

### 3. Report

Running `datawall` without arguments reads `~/.datawall/store.json` and
displays a Rich table with:

- Sent, received and total bytes per program
- Visual usage bar
- Current speed (live 1-second measurement)
- Daemon status

### 4. Historical reports

`datawall days 7` (or 30, 90, etc.) aggregates data across multiple days
from `store.json`, summing totals per program and showing an average per
day column.

### 5. Watch mode

`datawall watch` opens a real-time terminal UI (alternate screen, like
`top`/`htop`) that updates every 2 seconds, showing:

- **Per-process upload/download speeds** — sampled from `ss -tpin` with
  socket cache deltas and timing correction
- **Daily accumulated totals** — read live from `store.json` (reloaded
  each cycle, so daemon updates appear automatically)
- **Residual `unattributed` traffic** — interface traffic not captured by `ss`
- **Interface speed** — total up/down from `psutil.net_io_counters()`

The table is capped to what fits the terminal — the alternate screen
cannot scroll — and the remaining processes are folded into a single
`… +N more` row that keeps their combined speed and totals. Rows are
ordered by bytes used today, with current speed as the tiebreak.

Press `Ctrl+C` to exit.

### 6. Interface selection

datawall monitors one interface, chosen in this order:

1. `"interface"` in `~/.datawall/config.json`, if set
2. The interface holding the IPv4 default route (`/proc/net/route`)
3. The first non-virtual interface with traffic
4. The first non-virtual interface that is up

Loopback, `docker*`, `br-*`, `virbr*`, `veth*`, `vmnet*` and `vboxnet*`
are never auto-selected. The daemon re-checks the choice every 60
seconds, so a VPN going up or down is picked up without a restart.

Pin the interface manually by adding it to the config:

```json
{ "interface": "wlo1" }
```

Monitoring a physical NIC instead of the VPN tunnel measures what the
carrier actually bills, but inflates `unattributed` by the tunnel overhead.

### 7. Daily limit

`datawall limit 5GB` sets a daily traffic limit stored in
`~/.datawall/config.json`. The report and watch mode automatically
show a warning in the subtitle when the usage approaches or exceeds
the limit:

- **≥80%**: yellow warning `⚠ Near limit: 4.5 GB / 5.0 GB (90%)`
- **≥100%**: red warning `⚠ EXCEEDED: 6.2 GB / 5.0 GB (124%)`

The daemon does not enforce the limit — it is a purely visual alert
in the UI. Use `datawall limit off` to remove it.

### 8. Unattributed-traffic diagnostic

`datawall explain` answers "why is `unattributed` so large?" with
measurements rather than guesses. It samples for a few seconds and reports:

- **Where the bytes went** — interface bytes vs. bytes it could attribute
  to TCP sockets, and the residue.
- **Protocol mix** — TCP segment and UDP datagram rates, plus an estimate
  of TCP/IP header bytes that payload-only counters can never see.
- **Likely causes, ranked** — derived from what was actually observed: a
  tunnel below the monitored interface, a default route elsewhere, UDP
  outpacing TCP, header overhead, sockets with no visible owner.

Sample for longer while something is downloading to get a useful reading:

```bash
datawall explain 30
```

A few seconds on an idle link measures almost nothing, and the command
says so rather than reporting a meaningless 100%.

### 9. Connections viewer

`datawall connections` takes a snapshot of all active TCP sockets via
`ss -tpin` and groups them by `(program, remote_address:port)`, showing
sent/received bytes per remote endpoint with a percentage bar relative
to the program's total.

## Accuracy

| Component | Source | Accuracy |
|---|---|---|
| Daily total | `net_io_counters()` | **100%** |
| Per program (TCP) | `ss -tpin` socket delta | **~99%** |
| `unattributed` | Traffic no TCP socket explained — see below | Varies |

### What `unattributed` is

`unattributed` (called `other` before 1.1.0) is not a program. It is the
gap between what the interface counted and what the visible TCP sockets
could explain, in order of typical impact:

1. **A VPN below the monitored interface.** If the default route is a
   tunnel but a physical NIC is monitored, `ss` reports tunnel payload
   while the NIC counts the same traffic encapsulated and encrypted.
   The whole difference is unattributable. datawall monitors the
   default-route interface to avoid exactly this.
2. **UDP is not measured.** `ss -tpin` is TCP only, so QUIC/HTTP3
   (how browsers stream video today), DNS, DHCP, WireGuard and video
   calls all land here.
3. **Header overhead.** `net_io_counters()` counts full frames;
   `bytes_acked` counts payload only. ~5-10% structurally.
4. **Processes owned by other users or root.** Without privileges `ss`
   cannot map their sockets to a PID, so `apt`, `systemd-resolved` and
   `NetworkManager` traffic is unattributed.
5. **Short-lived sockets** that open and close between two samples.
6. Retransmissions, ICMP, ARP, multicast.

## Retention

The daemon keeps the last 90 days and drops older ones, so the store
cannot grow without bound. Change the window in
`~/.datawall/config.json`:

```json
{ "retention_days": 365 }
```

Pruning runs when the daemon starts and again at each date change.

## Store format

`~/.datawall/store.json` holds only durable history, and is written only
when the accumulated bytes actually change:

```json
{
  "days": {
    "2026-07-13": {
      "total_sent": 26000000,
      "total_recv": 140200000,
      "processes": {
        "firefox":      { "sent": 15200000, "recv": 82100000 },
        "discord":      { "sent": 2100000,  "recv": 12800000 },
        "unattributed": { "sent": 8700000,  "recv": 35300000 }
      }
    }
  }
}
```

The `unattributed` bucket was called `other` before 1.1.0. Existing
stores are migrated automatically on first read, and the counter
baselines and speed samples that used to be persisted here now live in
`~/.datawall/live.json`, which the report reads to show the current
speed without re-measuring it.

## Troubleshooting

**Daemon can't find a network interface:** Make sure you have an active
network interface (WiFi or ethernet). Loopback and virtual interfaces
(`docker*`, `br-*`, `virbr*`, `veth*`, `vmnet*`, `vboxnet*`) are never
auto-selected; pin one explicitly with `{"interface": "..."}` in
`~/.datawall/config.json` if detection picks the wrong one.

**Report shows 0 bytes:** The daemon needs at least 5 seconds to
accumulate data after starting. `datawall days N` will show 0 for
future dates with no data.

**`unattributed` has a high %:** Run `datawall explain 30` while
something is downloading — it measures the actual cause instead of
guessing. The most common one by far is a VPN tunnel sitting below the
monitored interface; see "Interface selection".

**Reset data:** `datawall reset` clears today's data.

## Development

### Project structure

```
datawall/
├── datawall                  # Main Python script (executable)
├── datawall.service          # systemd user unit
├── Makefile                  # Build helper
├── README.md                 # This file
├── README.es.md              # Spanish documentation
├── CHANGELOG.md              # Release notes
├── CHANGELOG.es.md           # Spanish release notes
├── .gitignore
├── pkg/
│   └── debian/
│       ├── control           # Debian package metadata
│       ├── postinst          # Post-installation script
│       └── prerm             # Pre-removal script
```

### Build .deb

```bash
make deb
```

Generates `datawall_1.1.0_all.deb`.

### Clean

```bash
make clean
```

## License

MIT
