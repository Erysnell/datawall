"""Store schema migration, retention pruning and write behaviour."""
import json
import time
import unittest
from datetime import date, timedelta

from helpers import IsolatedHomeTest


def legacy_store():
    """A store in the pre-1.1.0 schema: `other` plus persisted runtime state."""
    return {
        'days': {
            '2026-07-13': {
                'total_sent': 1000, 'total_recv': 4000,
                'processes': {
                    'firefox': {'sent': 600, 'recv': 2000},
                    'other': {'sent': 400, 'recv': 2000},
                },
                'last_tx': 123456, 'last_rx': 654321, 'last_time': 1752000000.0,
                'speed_sent': 12.5, 'speed_recv': 99.0,
            },
        },
    }


class TestMigration(IsolatedHomeTest):
    def migrate(self, data=None):
        return self.dw._migrate(data if data is not None else legacy_store())

    def test_other_is_renamed_to_unattributed(self):
        procs = self.migrate()['days']['2026-07-13']['processes']
        self.assertNotIn('other', procs)
        self.assertEqual(procs[self.dw.UNATTRIBUTED], {'sent': 400, 'recv': 2000})

    def test_totals_are_preserved(self):
        day = self.migrate()['days']['2026-07-13']
        self.assertEqual(day['total_sent'], 1000)
        self.assertEqual(day['total_recv'], 4000)
        self.assertEqual(sum(p['sent'] for p in day['processes'].values()), 1000)
        self.assertEqual(sum(p['recv'] for p in day['processes'].values()), 4000)

    def test_runtime_state_is_stripped(self):
        day = self.migrate()['days']['2026-07-13']
        for key in self.dw._VOLATILE_DAY_KEYS:
            self.assertNotIn(key, day)

    def test_other_merges_into_an_existing_unattributed_bucket(self):
        data = legacy_store()
        data['days']['2026-07-13']['processes'][self.dw.UNATTRIBUTED] = {'sent': 7, 'recv': 11}
        procs = self.migrate(data)['days']['2026-07-13']['processes']
        self.assertEqual(procs[self.dw.UNATTRIBUTED], {'sent': 407, 'recv': 2011})

    def test_is_idempotent(self):
        once = self.dw._migrate(legacy_store())
        twice = self.dw._migrate(self.dw._migrate(legacy_store()))
        self.assertEqual(json.dumps(once, sort_keys=True), json.dumps(twice, sort_keys=True))

    def test_tolerates_a_missing_days_key(self):
        self.assertEqual(self.dw._migrate({}), {'days': {}})

    def test_tolerates_a_malformed_day(self):
        data = {'days': {'2026-07-13': 'not a dict', '2026-07-14': {'processes': {}}}}
        self.assertEqual(self.dw._migrate(data), data)

    def test_runs_on_load_from_disk(self):
        self.dw.STORE_PATH.write_text(json.dumps(legacy_store()))
        procs = self.dw.DataStore().data['days']['2026-07-13']['processes']
        self.assertIn(self.dw.UNATTRIBUTED, procs)
        self.assertNotIn('other', procs)


class TestPrune(IsolatedHomeTest):
    def store_with_ages(self, *ages):
        store = self.dw.DataStore()
        store.data = {'days': {
            (date.today() - timedelta(days=a)).isoformat():
                {'total_sent': 1, 'total_recv': 1, 'processes': {}} for a in ages}}
        return store

    def test_drops_days_past_the_window(self):
        store = self.store_with_ages(0, 10, 89, 90, 200)
        self.assertEqual(store.prune(90), 2)
        self.assertEqual(len(store.data['days']), 3)

    def test_keeps_the_oldest_day_inside_the_window(self):
        store = self.store_with_ages(89)
        self.assertEqual(store.prune(90), 0)

    def test_drops_the_first_day_outside_the_window(self):
        store = self.store_with_ages(90)
        self.assertEqual(store.prune(90), 1)
        self.assertEqual(store.data['days'], {})

    def test_window_of_one_keeps_only_today(self):
        store = self.store_with_ages(0, 1)
        self.assertEqual(store.prune(1), 1)
        self.assertIn(date.today().isoformat(), store.data['days'])

    def test_non_positive_window_prunes_nothing(self):
        for window in (0, -5):
            store = self.store_with_ages(0, 500)
            self.assertEqual(store.prune(window), 0, window)
            self.assertEqual(len(store.data['days']), 2)


class TestSave(IsolatedHomeTest):
    def test_identical_content_is_not_rewritten(self):
        store = self.dw.DataStore()
        store.data = {'days': {'2026-01-01': {'total_sent': 1, 'total_recv': 1, 'processes': {}}}}
        store.save()
        first = self.dw.STORE_PATH.stat().st_mtime_ns
        time.sleep(0.02)
        store.save()
        self.assertEqual(self.dw.STORE_PATH.stat().st_mtime_ns, first)

    def test_changed_content_is_written(self):
        store = self.dw.DataStore()
        store.data = {'days': {'2026-01-01': {'total_sent': 1, 'total_recv': 1, 'processes': {}}}}
        store.save()
        first = self.dw.STORE_PATH.stat().st_mtime_ns
        store.data['days']['2026-01-01']['total_sent'] = 2
        time.sleep(0.02)
        store.save()
        self.assertNotEqual(self.dw.STORE_PATH.stat().st_mtime_ns, first)

    def test_leaves_no_temp_file_behind(self):
        store = self.dw.DataStore()
        store.get_today()
        store.save()
        self.assertFalse(self.dw.STORE_PATH.with_suffix('.tmp').exists())

    def test_written_file_is_valid_json(self):
        store = self.dw.DataStore()
        store.get_today()['total_sent'] = 5
        store.save()
        self.assertEqual(
            json.loads(self.dw.STORE_PATH.read_text())['days'][date.today().isoformat()]['total_sent'], 5)


class TestReloadIfChanged(IsolatedHomeTest):
    def test_picks_up_an_external_write(self):
        """The bug this guards: the daemon used to clobber `datawall reset`."""
        store = self.dw.DataStore()
        store.get_today()['total_sent'] = 999
        store.save()
        # another process wipes the day
        self.dw.STORE_PATH.write_text(json.dumps({'days': {}}))
        self.assertTrue(store.reload_if_changed())
        self.assertEqual(store.data['days'], {})

    def test_reports_no_change_after_its_own_save(self):
        store = self.dw.DataStore()
        store.get_today()['total_sent'] = 1
        store.save()
        self.assertFalse(store.reload_if_changed())

    def test_handles_a_missing_store_file(self):
        store = self.dw.DataStore()
        self.assertFalse(store.reload_if_changed())


class TestTodayAndReset(IsolatedHomeTest):
    def test_get_today_creates_a_day_with_the_current_schema(self):
        day = self.dw.DataStore().get_today()
        self.assertEqual(sorted(day), ['processes', 'total_recv', 'total_sent'])

    def test_reset_removes_todays_day(self):
        store = self.dw.DataStore()
        store.get_today()['total_sent'] = 50
        store.save()
        store.reset_today()
        self.assertNotIn(date.today().isoformat(), store.data['days'])
        self.assertNotIn(date.today().isoformat(),
                         json.loads(self.dw.STORE_PATH.read_text())['days'])

    def test_reset_leaves_other_days_alone(self):
        store = self.dw.DataStore()
        store.data['days']['2026-01-01'] = {'total_sent': 9, 'total_recv': 9, 'processes': {}}
        store.get_today()
        store.reset_today()
        self.assertIn('2026-01-01', store.data['days'])


class TestLiveState(IsolatedHomeTest):
    def test_round_trip(self):
        self.dw.write_live_state('eth9', 1234.56, 7890.12)
        live = self.dw.read_live_state(60)
        self.assertEqual(live['iface'], 'eth9')
        self.assertAlmostEqual(live['speed_sent'], 1234.6, places=1)
        self.assertAlmostEqual(live['speed_recv'], 7890.1, places=1)

    def test_stale_samples_are_rejected(self):
        self.dw.write_live_state('eth9', 1.0, 2.0)
        self.assertIsNone(self.dw.read_live_state(-1))

    def test_missing_file_returns_none(self):
        self.assertIsNone(self.dw.read_live_state(60))

    def test_corrupt_json_returns_none(self):
        self.dw.LIVE_PATH.write_text('{not json')
        self.assertIsNone(self.dw.read_live_state(60))

    def test_non_numeric_speeds_are_rejected(self):
        self.dw.LIVE_PATH.write_text(json.dumps(
            {'iface': 'x', 'speed_sent': 'fast', 'speed_recv': 1, 'time': time.time()}))
        self.assertIsNone(self.dw.read_live_state(60))

    def test_non_numeric_timestamp_is_rejected(self):
        self.dw.LIVE_PATH.write_text(json.dumps(
            {'iface': 'x', 'speed_sent': 1, 'speed_recv': 1, 'time': 'now'}))
        self.assertIsNone(self.dw.read_live_state(60))

    def test_a_null_interface_is_allowed(self):
        self.dw.write_live_state(None, 0.0, 0.0)
        self.assertIsNone(self.dw.read_live_state(60)['iface'])


if __name__ == '__main__':
    unittest.main()
