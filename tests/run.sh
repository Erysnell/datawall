#!/bin/sh
# Test runner. Fast suite by default; pass --all to include the integration
# tests that start a real daemon and move real bytes.
set -e
cd "$(dirname "$0")"

if [ "$1" = "--all" ]; then
    echo "Running every test, integration included (this takes minutes)."
    DATAWALL_SLOW_TESTS=1 exec python3 -m unittest discover -p 'test_*.py' -v
fi

exec python3 -m unittest discover -p 'test_*.py' "$@"
