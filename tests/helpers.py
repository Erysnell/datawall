"""Shared test scaffolding.

datawall is a single executable script with no .py extension, so it cannot be
imported normally. Every test module loads it through SourceFileLoader with
HOME already redirected, because the module computes DATA_DIR at import time.
"""
import importlib.machinery
import importlib.util
import os
import shutil
import subprocess
import tempfile
import unittest

SCRIPT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'datawall')


def load_datawall(home: str):
    """Import the script with DATA_DIR pointing inside `home`.

    HOME must be set before exec_module: DATA_DIR is a module-level constant.
    """
    os.environ['HOME'] = home
    os.makedirs(os.path.join(home, '.datawall'), exist_ok=True)
    loader = importlib.machinery.SourceFileLoader('datawall_under_test', SCRIPT)
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


class IsolatedHomeTest(unittest.TestCase):
    """Gives each test class a throwaway HOME and a freshly loaded module."""

    def setUp(self):
        self._real_home = os.environ.get('HOME')
        self.home = tempfile.mkdtemp(prefix='datawall-test-')
        self.dw = load_datawall(self.home)

    def tearDown(self):
        if self._real_home is not None:
            os.environ['HOME'] = self._real_home
        shutil.rmtree(self.home, ignore_errors=True)

    def write_config(self, data):
        import json
        self.dw.CONFIG_PATH.write_text(json.dumps(data))
        return self.dw.Config()


def spawn_dummy_process():
    """A harmless long-lived process to stand in for a daemon pid.

    Never use the test runner's own pid for this: anything that calls
    `datawall stop` would read the pid file and SIGTERM the test run itself.
    """
    return subprocess.Popen(['sleep', '600'])


def run_cli(home: str, *args, timeout: int = 60):
    """Invoke the script as a subprocess against an isolated HOME."""
    return subprocess.run(
        ['python3', SCRIPT, *args],
        env=dict(os.environ, HOME=home),
        capture_output=True, text=True, timeout=timeout,
    )


def have_network(host: str = 'cloudflare.com') -> bool:
    try:
        r = subprocess.run(['getent', 'hosts', host], capture_output=True, timeout=5)
        return r.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def slow_tests_enabled() -> bool:
    """Integration tests start a real daemon and move real bytes."""
    return os.environ.get('DATAWALL_SLOW_TESTS') == '1'


requires_slow = unittest.skipUnless(
    slow_tests_enabled(), 'set DATAWALL_SLOW_TESTS=1 to run integration tests')
