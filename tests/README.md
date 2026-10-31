# Tests

Plain `unittest` from the standard library — the project has no test
dependencies, so the suite runs anywhere `datawall` itself runs.

## Running

```bash
./tests/run.sh              # fast suite, no network, no daemon
./tests/run.sh --all        # adds the integration tests (minutes, needs network)
./tests/run.sh -v           # verbose
make test                   # same as run.sh
make test-all               # same as run.sh --all
```

A single module or case:

```bash
cd tests
python3 -m unittest test_store
python3 -m unittest test_store.TestMigration.test_is_idempotent
```

## Layout

| Module | Covers |
|---|---|
| `test_format.py` | `format_bytes`, `format_speed`, `parse_bytes`, interface classification |
| `test_parse_ss.py` | `parse_ss_output` against trimmed real `ss -tpin` output |
| `test_store.py` | Schema migration, retention pruning, conditional save, external-write reload, live state |
| `test_config.py` | Every config key, including validation and fallbacks |
| `test_notify.py` | Limit thresholds, message content, delivery-failure retry |
| `test_proc.py` | `/proc/net/{route,snmp,netstat}` parsers, driven by fixtures |
| `test_cli.py` | Exit codes, argument validation, report output |
| `test_daemon.py` | **Integration.** Real daemon, real counters, real traffic |

`helpers.py` holds the shared scaffolding.

## Why the loader dance

`datawall` is a single executable with no `.py` extension, so it cannot be
imported normally. `helpers.load_datawall()` loads it through
`SourceFileLoader` with `HOME` already pointed at a temporary directory —
that ordering matters, because the module computes `DATA_DIR` at import
time. Every test therefore runs against a throwaway `~/.datawall` and never
touches real data.

## The integration tests

`test_daemon.py` is skipped unless `DATAWALL_SLOW_TESTS=1`, and skips itself
again if there is no network, since it generates traffic by downloading a
few megabytes. It starts a real daemon per test case and stops it on
teardown. These are the only tests that can be affected by, or affect,
system state — they still use an isolated `HOME`, but desktop notifications
genuinely reach the desktop.
