"""Config reading, validation and fallbacks."""
import json
import unittest

from helpers import IsolatedHomeTest


class TestDailyLimit(IsolatedHomeTest):
    def test_absent_means_no_limit(self):
        self.assertIsNone(self.write_config({}).get_daily_limit())

    def test_positive_int_is_accepted(self):
        self.assertEqual(self.write_config({'daily_limit': 2048}).get_daily_limit(), 2048)

    def test_zero_and_negative_are_rejected(self):
        for value in (0, -1):
            self.assertIsNone(self.write_config({'daily_limit': value}).get_daily_limit(), value)

    def test_wrong_types_are_rejected(self):
        for value in ('5GB', None, [], 1.5):
            self.assertIsNone(self.write_config({'daily_limit': value}).get_daily_limit(), value)

    def test_set_and_remove_round_trip_through_disk(self):
        cfg = self.write_config({})
        cfg.set_daily_limit(4096)
        self.assertEqual(self.dw.Config().get_daily_limit(), 4096)
        cfg.remove_daily_limit()
        self.assertIsNone(self.dw.Config().get_daily_limit())


class TestInterfaceOverride(IsolatedHomeTest):
    def test_absent_means_autodetect(self):
        self.assertIsNone(self.write_config({}).get_interface())

    def test_name_is_returned(self):
        self.assertEqual(self.write_config({'interface': 'wlo1'}).get_interface(), 'wlo1')

    def test_empty_and_wrong_types_are_rejected(self):
        for value in ('', None, 0, ['eth0']):
            self.assertIsNone(self.write_config({'interface': value}).get_interface(), value)


class TestRetention(IsolatedHomeTest):
    def test_default_is_used_when_absent(self):
        self.assertEqual(self.write_config({}).get_retention_days(),
                         self.dw.DEFAULT_RETENTION_DAYS)

    def test_positive_int_is_accepted(self):
        self.assertEqual(self.write_config({'retention_days': 365}).get_retention_days(), 365)

    def test_invalid_values_fall_back_to_the_default(self):
        for value in (0, -3, 'many', None, 1.5):
            self.assertEqual(self.write_config({'retention_days': value}).get_retention_days(),
                             self.dw.DEFAULT_RETENTION_DAYS, value)


class TestNotificationConfig(IsolatedHomeTest):
    def test_enabled_by_default(self):
        self.assertTrue(self.write_config({}).notifications_enabled())

    def test_only_an_explicit_false_disables(self):
        self.assertFalse(self.write_config({'notifications': False}).notifications_enabled())
        self.assertTrue(self.write_config({'notifications': True}).notifications_enabled())
        self.assertTrue(self.write_config({'notifications': 'no'}).notifications_enabled())

    def test_default_thresholds(self):
        self.assertEqual(self.write_config({}).get_notify_thresholds(),
                         list(self.dw.DEFAULT_NOTIFY_THRESHOLDS))

    def test_custom_thresholds_are_sorted_and_deduplicated(self):
        cfg = self.write_config({'notify_thresholds': [100, 50, 90, 50]})
        self.assertEqual(cfg.get_notify_thresholds(), [50, 90, 100])

    def test_floats_are_coerced_to_int(self):
        self.assertEqual(self.write_config({'notify_thresholds': [75.6]}).get_notify_thresholds(), [75])

    def test_out_of_range_and_garbage_entries_are_dropped(self):
        cfg = self.write_config({'notify_thresholds': [0, -10, 'x', None, 20000, 80]})
        self.assertEqual(cfg.get_notify_thresholds(), [80])

    def test_booleans_are_not_treated_as_numbers(self):
        """True would otherwise sneak in as the threshold 1."""
        cfg = self.write_config({'notify_thresholds': [True, False]})
        self.assertEqual(cfg.get_notify_thresholds(), list(self.dw.DEFAULT_NOTIFY_THRESHOLDS))

    def test_empty_or_wrong_type_falls_back_to_the_default(self):
        for value in ([], 'all', None, {}):
            self.assertEqual(self.write_config({'notify_thresholds': value}).get_notify_thresholds(),
                             list(self.dw.DEFAULT_NOTIFY_THRESHOLDS), value)


class TestConfigRobustness(IsolatedHomeTest):
    def test_corrupt_file_degrades_to_defaults_instead_of_raising(self):
        self.dw.CONFIG_PATH.write_text('{not json')
        cfg = self.dw.Config()
        self.assertIsNone(cfg.get_daily_limit())
        self.assertEqual(cfg.get_retention_days(), self.dw.DEFAULT_RETENTION_DAYS)

    def test_missing_file_degrades_to_defaults(self):
        self.assertIsNone(self.dw.Config().get_daily_limit())

    def test_save_preserves_unrelated_keys(self):
        cfg = self.write_config({'interface': 'wlo1', 'retention_days': 7})
        cfg.set_daily_limit(1024)
        on_disk = json.loads(self.dw.CONFIG_PATH.read_text())
        self.assertEqual(on_disk['interface'], 'wlo1')
        self.assertEqual(on_disk['retention_days'], 7)
        self.assertEqual(on_disk['daily_limit'], 1024)


if __name__ == '__main__':
    unittest.main()
