# datawall — Network data usage tracker per program

> **Español:** También disponible en [español](README.es.md).

Per-process network traffic monitor for Linux. Displays each program's
daily sent/received data in a formatted terminal table with visual bars
and current transfer speed.

```
╭─────────────────────────── DataWall — 2026-07-13 ────────────────────────────╮
│                                                                              │
│  ┏━━━━━━━━━━┳━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━┓           │
│  ┃ Program  ┃    Sent ┃ Received ┃    Total ┃ %                 ┃           │
│  ┣━━━━━━━━━━╋━━━━━━━━━╋━━━━━━━━━━╋━━━━━━━━━━╋━━━━━━━━━━━━━━━━━━━┫           │
│  ┃ firefox  ┃ 15.2 MB ┃  82.1 MB ┃  97.3 MB ┃ ████████░░  62.2% ┃           │
│  ┃ discord  ┃  2.1 MB ┃  12.8 MB ┃  14.9 MB ┃ ██░░░░░░░░   9.6% ┃           │
│  ┃ other    ┃  8.7 MB ┃  35.3 MB ┃  44.0 MB ┃ ███░░░░░░░  28.2% ┃           │
│  ┃ TOTAL    ┃ 26.0 MB ┃ 140.2 MB ┃ 166.2 MB ┃                   ┃           │
│  ┗━━━━━━━━━━┻━━━━━━━━━┻━━━━━━━━━━┻━━━━━━━━━━┻━━━━━━━━━━━━━━━━━━━┛           │
│                                                                              │
╰──────────────────── Speed:  ↑ 1.2 MB/s  ↓ 3.8 MB/s   [wlo1] ────────────────╯
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
sudo apt install ./datawall_1.0.0_all.deb
```

Or with dpkg (dependencies must be resolved manually):

```bash
sudo dpkg -i datawall_1.0.0_all.deb
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

## Accuracy

| Component | Source | Accuracy |
|---|---|---|
| Daily total | `net_io_counters()` | **100%** |
| Per program (TCP) | `ss -tpin` socket delta | **~99%** |
| "other" | Unattributed traffic (UDP, short-lived connections between samples, retransmissions) | Varies |

## Store format

Data is stored in `~/.datawall/store.json`:

```json
{
  "days": {
    "2026-07-13": {
      "total_sent": 26000000,
      "total_recv": 140200000,
      "processes": {
        "firefox": { "sent": 15200000, "recv": 82100000 },
        "discord": { "sent": 2100000,  "recv": 12800000 },
        "other":   { "sent": 8700000,  "recv": 35300000 }
      }
    }
  }
}
```

## Troubleshooting

**Daemon can't find a network interface:** Make sure you have an active
network interface (WiFi or ethernet). Loopback (`lo`) is ignored.

**Report shows 0 bytes:** The daemon needs at least 5 seconds to
accumulate data after starting.

**"other" has a high %:** Normal during the first few samples. Over time
the percentage stabilizes at a low value. A sustained high % indicates
UDP traffic or very short-lived connections (API calls, DNS).

**Reset data:** `datawall reset` clears today's data.

## Development

### Project structure

```
datawall/
├── datawall                  # Main Python script (executable)
├── datawall.service          # systemd user unit
├── Makefile                  # Build helper
├── README.md                 # This file
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

Generates `datawall_1.0.0_all.deb`.

### Clean

```bash
make clean
```

## License

MIT
