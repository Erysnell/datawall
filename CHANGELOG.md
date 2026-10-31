# Changelog

All notable changes to this project are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.0] - 2026-10-31

Bug-fix and diagnostics release. Every 1.0.0 command keeps working
identically and existing stores are migrated automatically, so no manual
steps are needed when upgrading.

### Added

- `datawall explain [SECONDS]` — measures where `unattributed` traffic comes
  from instead of guessing. Samples the interface, compares it against what
  it could attribute to TCP sockets, reads the TCP/UDP mix from
  `/proc/net/snmp`, and ranks the likely causes by severity. Says so
  explicitly when the sample was too small to conclude anything.
- `datawall --version`.
- `interface` config key, to pin the monitored interface when auto-detection
  picks the wrong one.
- `retention_days` config key (default 90).
- `~/.datawall/live.json`, holding the daemon's current speed and monitored
  interface for readers to consume.

### Changed

- **The `other` bucket is now called `unattributed`.** Existing stores are
  migrated on first read: the counters are merged, totals are preserved, and
  the migration is idempotent.
- **Interface selection** now prefers the IPv4 default route
  (`/proc/net/route`) over whichever interface the kernel happened to list
  first, never auto-selects loopback or virtual interfaces (`docker*`,
  `br-*`, `virbr*`, `veth*`, `vmnet*`, `vboxnet*`), and is re-checked every
  60 seconds so a VPN going up or down is picked up without a restart.
- **`store.json` holds only durable history** and is written only when the
  accumulated bytes actually change. The counter baselines and speed samples
  it used to persist every 5 seconds — and that nothing ever read — moved to
  `live.json`. The baseline is now daemon-local, so a restart re-seeds it
  instead of attributing traffic that moved while nothing was watching.
- The daemon prunes days past the retention window at startup and at each
  date change, so the store can no longer grow without bound.
- The daily report reads the current speed from `live.json` when it is fresh
  rather than spending a second measuring it again (1.21s to 0.21s locally).
- The report prints a one-line pointer to `datawall explain` when
  `unattributed` exceeds 15% of the total.
- Watch mode caps its table to what fits the terminal and folds the rest into
  a single `… +N more` row that keeps the combined speed and totals. Rows are
  ordered by bytes used today with current speed as the tiebreak.
- `prerm` now stops daemons through a pid-file sweep that verifies the process
  before signalling it, with `pkill` as a fallback rather than the primary
  mechanism.
- `Makefile` derives the package version from the `VERSION` constant in the
  script and injects it into the package metadata at build time, so the
  version lives in exactly one place. `make version` reports it and fails if
  it cannot be read.
- The package declares `iproute2` as a dependency; `ss` is required for
  per-process tracking.
- `datawall.service` documentation URL now points at this project instead of
  an unrelated repository.

### Fixed

- **`datawall reset` reverted itself within 5 seconds.** The daemon held one
  in-memory copy of the store for its whole lifetime and wrote the stale day
  straight back over the reset. It now re-reads the store when another
  process has written it.
- **`datawall days N` crashed** with `ZeroDivisionError` when no day in the
  window had data.
- **A phantom multi-gigabyte delta** could be recorded when an interface
  disappeared and came back: the failed read stored a zero baseline, which
  the next sample read back as the full cumulative counter.
- Watch mode's table grew for the whole day and was cropped silently by the
  alternate screen, with no way to scroll.
- Watch mode's sort key compared percentages against bytes per second, so a
  process with current traffic jumped above everything else.
- Watch mode showed the daemon status as computed once at startup, so the
  subtitle was wrong for the rest of the session.
- The monitored interface name never appeared in the report subtitle: Rich
  parsed `[wlo1]` as a style tag and discarded it.
- `prerm`'s `pkill` pattern was anchored to `^python3 `, which never matched
  the packaged daemon — a shebang makes the command line
  `/usr/bin/python3 /usr/bin/datawall run`.

## [1.0.0] - 2026-07-20

First packaged release.

### Added

- Sampling daemon that reads kernel network counters every 5 seconds and
  attributes the delta to processes via exact per-socket byte counters from
  `ss -tpin` (SOCK_DIAG), falling back to proportional attribution by
  connection count when `ss` is unavailable.
- Daily report with per-program sent/received/total, usage bars and current
  transfer speed.
- `datawall watch` — real-time per-process bandwidth monitor.
- `datawall days N` — aggregated report for the last N days with a daily
  average.
- `datawall limit` — daily traffic limit with visual warnings at 80% and
  100%.
- `datawall connections` — active TCP connections grouped by program and
  remote address.
- Daemon lifecycle commands (`start`, `run`, `stop`, `restart`, `status`) and
  `reset`.
- Debian packaging and a systemd user unit.

[1.1.0]: https://github.com/Erysnell/datawall/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/Erysnell/datawall/releases/tag/v1.0.0
