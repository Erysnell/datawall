"""Integration tests: a real daemon, real interface counters, real bytes.

Skipped unless DATAWALL_SLOW_TESTS=1, because they take minutes and download
a few megabytes. Run them with:

    DATAWALL_SLOW_TESTS=1 python3 -m unittest test_daemon
"""
import json
import os
import shutil
import subprocess
import tempfile
import time
import unittest
from datetime import date, timedelta

from helpers import (have_network, load_datawall, requires_slow, run_cli,
                     spawn_dummy_process)


def _alive(pid):
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False

TODAY = date.today().isoformat()
VOLATILE = ('last_tx', 'last_rx', 'last_time', 'speed_sent', 'speed_recv')


@requires_slow
class DaemonTest(unittest.TestCase):
    """Each test gets its own HOME and its own daemon, stopped on teardown."""

    limit_bytes = None
    config = None

    def setUp(self):
        if not have_network():
            self.skipTest('no network: cannot generate traffic')
        self._real_home = os.environ.get('HOME')
        self.home = tempfile.mkdtemp(prefix='datawall-daemon-')
        self.dw = load_datawall(self.home)
        cfg = dict(self.config or {})
        if self.limit_bytes:
            cfg['daily_limit'] = self.limit_bytes
        if cfg:
            self.dw.CONFIG_PATH.write_text(json.dumps(cfg))

    def tearDown(self):
        self.cli('stop')
        if self._real_home is not None:
            os.environ['HOME'] = self._real_home
        shutil.rmtree(self.home, ignore_errors=True)

    # ── helpers ──
    def cli(self, *args):
        try:
            return run_cli(self.home, *args)
        except subprocess.TimeoutExpired:
            return None

    def start(self):
        self.cli('start')
        self.assertTrue(self.wait(lambda: self.dw.LIVE_PATH.exists(), 30),
                        'daemon never published live state')

    def traffic(self, mb=8):
        subprocess.run(
            ['curl', '-s', '-o', '/dev/null', '--max-time', '30',
             f'https://speed.cloudflare.com/__down?bytes={mb * 1_000_000}'],
            env=dict(os.environ, HOME=self.home), capture_output=True)

    @staticmethod
    def wait(predicate, timeout, interval=1.0):
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                if predicate():
                    return True
            except (OSError, ValueError, KeyError, json.JSONDecodeError):
                pass
            time.sleep(interval)
        return False

    def day(self):
        try:
            return json.loads(self.dw.STORE_PATH.read_text())['days'].get(TODAY)
        except (OSError, json.JSONDecodeError, KeyError):
            return None

    def total(self):
        d = self.day()
        return 0 if not d else d.get('total_sent', 0) + d.get('total_recv', 0)

    def log(self):
        try:
            return self.dw.LOG_PATH.read_text()
        except OSError:
            return ''


class TestAccumulation(DaemonTest):
    def test_traffic_is_accumulated_and_attributed(self):
        self.start()
        self.traffic()
        self.assertTrue(self.wait(lambda: self.total() > 0, 30), 'nothing accumulated')
        day = self.day()
        self.assertTrue(day['processes'], 'no per-process attribution at all')

    def test_the_store_holds_no_runtime_state(self):
        self.start()
        self.traffic()
        self.wait(lambda: self.total() > 0, 30)
        for key in VOLATILE:
            self.assertNotIn(key, self.day(), f'{key} leaked into the history')

    def test_live_state_is_published_and_fresh(self):
        self.start()
        live = self.dw.read_live_state(60)
        self.assertIsNotNone(live, 'live state missing or stale')
        self.assertIsInstance(live['speed_recv'], (int, float))

    def test_the_legacy_other_bucket_is_not_recreated(self):
        self.start()
        self.traffic()
        self.wait(lambda: self.total() > 0, 30)
        self.assertNotIn('other', self.day()['processes'])


class TestResetPersists(DaemonTest):
    """The headline bug: the daemon used to rewrite the day it had cached."""

    def test_an_external_write_survives_the_next_save(self):
        self.start()
        self.traffic()
        self.assertTrue(self.wait(lambda: self.total() > 0, 30))
        data = json.loads(self.dw.STORE_PATH.read_text())
        data['days'][TODAY]['processes']['SENTINEL'] = {'sent': 1, 'recv': 1}
        self.dw.STORE_PATH.write_text(json.dumps(data))
        time.sleep(12)   # at least two daemon cycles
        self.assertIn('SENTINEL', self.day()['processes'],
                      'the daemon clobbered an external write')

    def test_reset_is_not_undone(self):
        self.start()
        self.traffic(20)
        self.assertTrue(self.wait(lambda: self.total() > 1_000_000, 40))
        before = self.total()
        self.cli('reset')
        time.sleep(13)
        self.assertLess(self.total(), before / 2,
                        f'the day came back: {before} -> {self.total()}')


class TestLimitNotifications(DaemonTest):
    limit_bytes = 1024 * 1024          # 1 MB, so ordinary traffic blows past both

    def test_both_thresholds_fire_once_each(self):
        if not self.dw.notify_available():
            self.skipTest('notify-send not installed')
        self.start()
        self.traffic()
        self.assertTrue(self.wait(lambda: self.day().get('notified') == [80, 100], 40),
                        f"thresholds not recorded: {(self.day() or {}).get('notified')}")
        self.assertEqual(self.log().count('Notified'), 2)

    def test_a_restart_does_not_repeat_them(self):
        if not self.dw.notify_available():
            self.skipTest('notify-send not installed')
        self.start()
        self.traffic()
        self.assertTrue(self.wait(lambda: self.day().get('notified') == [80, 100], 40))
        self.cli('restart')
        self.traffic(5)
        time.sleep(10)
        self.assertEqual(self.log().count('Notified'), 2,
                         'thresholds fired again after a restart')
        self.assertEqual(self.day()['notified'], [80, 100])


class TestNotificationsDisabled(DaemonTest):
    limit_bytes = 1024
    config = {'notifications': False}

    def test_nothing_is_sent_when_disabled(self):
        self.start()
        self.traffic(2)
        self.wait(lambda: self.total() > 0, 30)
        time.sleep(6)
        self.assertNotIn('Notified', self.log())
        self.assertEqual(self.day().get('notified', []), [])


class TestStatusAgainstARealDaemon(DaemonTest):
    def test_a_live_daemon_reports_as_sampling(self):
        self.start()
        r = self.cli('status')
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn('sampling normally', r.stdout)

    def test_status_reports_stopped_after_a_stop(self):
        self.start()
        self.cli('stop')
        r = self.cli('status')
        self.assertEqual(r.returncode, 1)
        self.assertIn('stopped', r.stdout)

    def test_a_live_process_with_an_aged_sample_reads_as_stalled(self):
        """SIGKILL skips the cleanup handler, so the pid file survives while
        live.json ages — exactly the silent death this must detect."""
        self.start()
        pid = int(self.dw.PID_PATH.read_text().strip())
        os.kill(pid, 9)
        self.assertTrue(self.wait(lambda: not _alive(pid), 10))
        # The pid file outlives a SIGKILL. Stand a throwaway process in for
        # the dead daemon rather than our own pid, which `stop` would signal.
        proc = spawn_dummy_process()
        self.addCleanup(lambda: (proc.kill(), proc.wait()))
        self.dw.PID_PATH.write_text(str(proc.pid))
        live = json.loads(self.dw.LIVE_PATH.read_text())
        live['time'] -= 3600
        self.dw.LIVE_PATH.write_text(json.dumps(live))
        r = self.cli('status')
        self.assertEqual(r.returncode, 2, r.stdout)
        self.assertIn('has not sampled', r.stdout)


class TestPruneOnStartup(DaemonTest):
    config = {'retention_days': 2}

    def test_days_outside_the_window_are_dropped(self):
        old = (date.today() - timedelta(days=30)).isoformat()
        keep = (date.today() - timedelta(days=1)).isoformat()
        self.dw.STORE_PATH.write_text(json.dumps({'days': {
            old: {'total_sent': 1, 'total_recv': 1, 'processes': {}},
            keep: {'total_sent': 1, 'total_recv': 1, 'processes': {}},
        }}))
        self.start()
        self.assertTrue(self.wait(
            lambda: old not in json.loads(self.dw.STORE_PATH.read_text())['days'], 30),
            'old day was not pruned')
        self.assertIn(keep, json.loads(self.dw.STORE_PATH.read_text())['days'])


if __name__ == '__main__':
    unittest.main()
