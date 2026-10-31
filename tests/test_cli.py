"""CLI surface: exit codes, argument validation, output shape.

These run the script as a subprocess against an isolated HOME. They need no
network and start no daemon.
"""
import json
import time
import unittest
from datetime import date

from helpers import IsolatedHomeTest, run_cli, spawn_dummy_process


class CliTest(IsolatedHomeTest):
    def cli(self, *args, **kw):
        return run_cli(self.home, *args, **kw)

    def seed_store(self, procs=None, notified=None):
        procs = procs or {'firefox': {'sent': 1000, 'recv': 4000}}
        day = {'total_sent': sum(p['sent'] for p in procs.values()),
               'total_recv': sum(p['recv'] for p in procs.values()),
               'processes': procs}
        if notified:
            day['notified'] = notified
        self.dw.STORE_PATH.write_text(json.dumps({'days': {date.today().isoformat(): day}}))

    def seed_live(self, iface='eth9'):
        self.dw.LIVE_PATH.write_text(json.dumps(
            {'iface': iface, 'speed_sent': 1024.0, 'speed_recv': 2048.0, 'time': time.time()}))


class TestVersion(CliTest):
    def test_version_flag_prints_the_constant(self):
        r = self.cli('--version')
        self.assertEqual(r.returncode, 0)
        self.assertEqual(r.stdout.strip(), f'datawall {self.dw.VERSION}')


class TestArgumentValidation(CliTest):
    def test_days_without_a_number_fails(self):
        r = self.cli('days')
        self.assertEqual(r.returncode, 1)
        self.assertIn('usage', r.stdout + r.stderr)

    def test_days_with_a_non_number_fails(self):
        self.assertEqual(self.cli('days', 'abc').returncode, 1)

    def test_days_with_zero_fails(self):
        self.assertEqual(self.cli('days', '0').returncode, 1)

    def test_explain_with_a_non_number_fails(self):
        r = self.cli('explain', 'abc')
        self.assertEqual(r.returncode, 1)
        self.assertIn('usage', r.stdout + r.stderr)

    def test_an_unknown_command_is_rejected(self):
        self.assertNotEqual(self.cli('frobnicate').returncode, 0)

    def test_an_invalid_limit_size_fails(self):
        r = self.cli('limit', '5 potatoes')
        self.assertEqual(r.returncode, 1)
        self.assertIn('invalid size', r.stdout + r.stderr)


class TestReport(CliTest):
    def test_renders_an_empty_store_without_crashing(self):
        self.seed_live()
        r = self.cli()
        self.assertEqual(r.returncode, 0)
        self.assertIn('TOTAL', r.stdout)

    def test_shows_program_rows(self):
        self.seed_store()
        self.seed_live()
        r = self.cli()
        self.assertIn('firefox', r.stdout)

    def test_uses_the_interface_name_from_live_state(self):
        """Regression: Rich used to eat `[eth9]` as a style tag."""
        self.seed_store()
        self.seed_live(iface='eth9')
        self.assertIn('eth9', self.cli().stdout)

    def test_points_at_explain_when_unattributed_dominates(self):
        self.seed_store({'firefox': {'sent': 100, 'recv': 100},
                         self.dw.UNATTRIBUTED: {'sent': 400, 'recv': 400}})
        self.seed_live()
        self.assertIn('datawall explain', self.cli().stdout)

    def test_stays_quiet_when_unattributed_is_small(self):
        self.seed_store({'firefox': {'sent': 1000, 'recv': 1000},
                         self.dw.UNATTRIBUTED: {'sent': 1, 'recv': 1}})
        self.seed_live()
        self.assertNotIn('datawall explain', self.cli().stdout)


class TestDaysReport(CliTest):
    def test_no_matching_days_does_not_divide_by_zero(self):
        """Regression: `days N` used to raise ZeroDivisionError."""
        r = self.cli('days', '3')
        self.assertEqual(r.returncode, 0)
        self.assertIn('Days with data: 0/3', r.stdout)

    def test_counts_the_days_that_have_data(self):
        self.seed_store()
        r = self.cli('days', '7')
        self.assertEqual(r.returncode, 0)
        self.assertIn('Days with data: 1/7', r.stdout)

    def test_a_huge_window_is_accepted(self):
        self.seed_store()
        self.assertEqual(self.cli('days', '4000').returncode, 0)


class TestLimitCommand(CliTest):
    def test_reports_when_no_limit_is_set(self):
        self.assertIn('no daily limit', self.cli('limit').stdout)

    def test_sets_and_reports_a_limit(self):
        self.assertEqual(self.cli('limit', '500MB').returncode, 0)
        out = self.cli('limit').stdout
        self.assertIn('500.0 MB', out)
        self.assertIn('notifications:', out)

    def test_removes_a_limit(self):
        self.cli('limit', '500MB')
        self.cli('limit', 'off')
        self.assertIn('no daily limit', self.cli('limit').stdout)

    def test_reports_notifications_disabled_by_config(self):
        self.cli('limit', '500MB')
        cfg = json.loads(self.dw.CONFIG_PATH.read_text())
        cfg['notifications'] = False
        self.dw.CONFIG_PATH.write_text(json.dumps(cfg))
        self.assertIn('disabled in config', self.cli('limit').stdout)

    def test_reports_the_configured_thresholds(self):
        self.cli('limit', '500MB')
        cfg = json.loads(self.dw.CONFIG_PATH.read_text())
        cfg['notify_thresholds'] = [25, 50]
        self.dw.CONFIG_PATH.write_text(json.dumps(cfg))
        out = self.cli('limit').stdout
        self.assertIn('25%', out)
        self.assertIn('50%', out)


class TestStatus(CliTest):
    """`status` must tell a healthy daemon apart from one that stopped
    sampling while its process stayed alive — the failure mode where a dead
    daemon looks fine for hours. Exit codes: 0 sampling, 1 stopped, 2 stalled.
    """

    @staticmethod
    def _reap(proc):
        proc.kill()
        proc.wait()

    def fake_daemon(self, sample_age=None):
        """Point the pid file at a live throwaway process."""
        proc = spawn_dummy_process()
        self.addCleanup(self._reap, proc)
        self.dw.PID_PATH.write_text(str(proc.pid))
        self.pid = proc.pid
        if sample_age is not None:
            self.dw.LIVE_PATH.write_text(json.dumps(
                {'iface': 'wlo1', 'speed_sent': 1024.0, 'speed_recv': 2048.0,
                 'time': time.time() - sample_age}))

    # ── stopped ──
    def test_stopped_with_no_pid_file(self):
        r = self.cli('status')
        self.assertEqual(r.returncode, 1)
        self.assertIn('stopped', r.stdout)

    def test_stopped_suggests_how_to_start(self):
        self.assertIn('datawall start', self.cli('status').stdout)

    def test_a_stale_pid_file_is_cleaned_up(self):
        self.dw.PID_PATH.write_text('999999999')
        r = self.cli('status')
        self.assertEqual(r.returncode, 1)
        self.assertIn('stopped', r.stdout)
        self.assertFalse(self.dw.PID_PATH.exists())

    def test_a_garbage_pid_file_reports_stopped_without_a_traceback(self):
        self.dw.PID_PATH.write_text('not-a-pid')
        r = self.cli('status')
        self.assertEqual(r.returncode, 1)
        self.assertNotIn('Traceback', r.stderr)

    # ── running and sampling ──
    def test_running_and_sampling_exits_zero(self):
        self.fake_daemon(sample_age=2)
        r = self.cli('status')
        self.assertEqual(r.returncode, 0)
        self.assertIn('sampling normally', r.stdout)

    def test_running_reports_the_pid(self):
        self.fake_daemon(sample_age=2)
        self.assertIn(str(self.pid), self.cli('status').stdout)

    def test_running_reports_sample_age_interface_and_speed(self):
        self.fake_daemon(sample_age=2)
        out = self.cli('status').stdout
        self.assertIn('last sample', out)
        self.assertIn('2s ago', out)
        self.assertIn('wlo1', out)
        self.assertIn('1.0 KB/s', out)
        self.assertIn('2.0 KB/s', out)

    # ── alive but stalled ──
    def test_a_stalled_daemon_exits_two(self):
        self.fake_daemon(sample_age=8040)        # 2h 14m
        r = self.cli('status')
        self.assertEqual(r.returncode, 2)
        self.assertIn('has not sampled in 2h 14m', r.stdout)

    def test_a_stalled_daemon_suggests_a_restart(self):
        self.fake_daemon(sample_age=8040)
        self.assertIn('datawall restart', self.cli('status').stdout)

    def test_a_daemon_that_never_sampled_is_stalled(self):
        self.fake_daemon()                       # pid alive, no live.json
        r = self.cli('status')
        self.assertEqual(r.returncode, 2)
        self.assertIn('never published a sample', r.stdout)

    def test_a_stalled_daemon_omits_the_speed_line(self):
        """Reporting a speed from a two-hour-old sample would be a lie."""
        self.fake_daemon(sample_age=8040)
        self.assertNotIn('speed:', self.cli('status').stdout)

    def test_the_boundary_is_three_sample_intervals(self):
        self.fake_daemon(sample_age=self.dw.STALL_AFTER - 2)
        self.assertEqual(self.cli('status').returncode, 0)
        self.fake_daemon(sample_age=self.dw.STALL_AFTER + 2)
        self.assertEqual(self.cli('status').returncode, 2)

    # ── usage line ──
    def test_usage_is_reported_against_the_limit(self):
        self.seed_store({'firefox': {'sent': 100, 'recv': 100}})
        self.cli('limit', '1000')
        self.fake_daemon(sample_age=2)
        self.assertIn('200.0 B of 1000.0 B limit', self.cli('status').stdout)

    def test_usage_is_reported_without_a_limit(self):
        self.seed_store({'firefox': {'sent': 100, 'recv': 100}})
        self.fake_daemon(sample_age=2)
        out = self.cli('status').stdout
        self.assertIn('200.0 B', out)
        self.assertNotIn('limit', out)

    def test_a_corrupt_live_file_is_treated_as_no_sample(self):
        self.fake_daemon()
        self.dw.LIVE_PATH.write_text('{not json')
        self.assertEqual(self.cli('status').returncode, 2)


class TestReset(CliTest):
    def test_reset_clears_today(self):
        self.seed_store()
        self.assertEqual(self.cli('reset').returncode, 0)
        self.assertNotIn(date.today().isoformat(),
                         json.loads(self.dw.STORE_PATH.read_text())['days'])

    def test_stop_without_a_daemon_is_not_an_error(self):
        r = self.cli('stop')
        self.assertEqual(r.returncode, 0)
        self.assertIn('not running', r.stdout)


class TestCorruptStore(CliTest):
    def test_a_corrupt_store_does_not_prevent_reporting(self):
        self.dw.STORE_PATH.write_text('{not json')
        self.seed_live()
        self.assertEqual(self.cli().returncode, 0)


if __name__ == '__main__':
    unittest.main()
