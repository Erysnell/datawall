"""Byte/speed formatting and size parsing."""
import unittest

from helpers import IsolatedHomeTest


class TestFormatBytes(IsolatedHomeTest):
    def test_units_scale_by_1024(self):
        f = self.dw.format_bytes
        self.assertEqual(f(0), '0.0 B')
        self.assertEqual(f(512), '512.0 B')
        self.assertEqual(f(1024), '1.0 KB')
        self.assertEqual(f(1024 ** 2), '1.0 MB')
        self.assertEqual(f(1024 ** 3), '1.0 GB')
        self.assertEqual(f(1024 ** 4), '1.0 TB')
        self.assertEqual(f(1024 ** 5), '1.0 PB')

    def test_petabytes_do_not_overflow_the_unit_list(self):
        self.assertEqual(self.dw.format_bytes(1024 ** 6), '1024.0 PB')

    def test_negative_values_keep_their_sign(self):
        self.assertEqual(self.dw.format_bytes(-2048), '-2.0 KB')

    def test_speed_appends_per_second(self):
        self.assertEqual(self.dw.format_speed(1024), '1.0 KB/s')


class TestFormatDuration(IsolatedHomeTest):
    def test_seconds_below_a_minute(self):
        f = self.dw.format_duration
        self.assertEqual(f(0), '0s')
        self.assertEqual(f(5), '5s')
        self.assertEqual(f(59), '59s')

    def test_minutes_and_seconds(self):
        self.assertEqual(self.dw.format_duration(60), '1m 0s')
        self.assertEqual(self.dw.format_duration(130), '2m 10s')
        self.assertEqual(self.dw.format_duration(3599), '59m 59s')

    def test_hours_and_minutes(self):
        self.assertEqual(self.dw.format_duration(3600), '1h 0m')
        self.assertEqual(self.dw.format_duration(8040), '2h 14m')

    def test_days_and_hours(self):
        self.assertEqual(self.dw.format_duration(86400), '1d 0h')
        self.assertEqual(self.dw.format_duration(183600), '2d 3h')

    def test_fractional_seconds_truncate(self):
        self.assertEqual(self.dw.format_duration(5.9), '5s')

    def test_negative_durations_clamp_to_zero(self):
        self.assertEqual(self.dw.format_duration(-10), '0s')


class TestParseBytes(IsolatedHomeTest):
    def test_suffixes(self):
        p = self.dw.parse_bytes
        self.assertEqual(p('1b'), 1)
        self.assertEqual(p('1kb'), 1024)
        self.assertEqual(p('500MB'), 500 * 1024 ** 2)
        self.assertEqual(p('5GB'), 5 * 1024 ** 3)
        self.assertEqual(p('2tb'), 2 * 1024 ** 4)

    def test_case_and_whitespace_are_ignored(self):
        self.assertEqual(self.dw.parse_bytes('  5 Gb '), 5 * 1024 ** 3)

    def test_fractional_values_truncate_to_int(self):
        self.assertEqual(self.dw.parse_bytes('1.5GB'), int(1.5 * 1024 ** 3))

    def test_bare_number_is_bytes(self):
        self.assertEqual(self.dw.parse_bytes('2048'), 2048)

    def test_off_aliases_mean_zero(self):
        for word in ('off', 'none', '0', 'OFF'):
            self.assertEqual(self.dw.parse_bytes(word), 0, word)

    def test_garbage_raises_with_a_usable_message(self):
        for bad in ('abc', '', 'GB', '5 potatoes', '1.2.3MB'):
            with self.assertRaises(ValueError) as cm:
                self.dw.parse_bytes(bad)
            self.assertIn('invalid size', str(cm.exception), bad)


class TestInterfaceClassification(IsolatedHomeTest):
    def test_virtual_interfaces_are_recognised(self):
        for name in ('lo', 'docker0', 'br-abc123', 'virbr0', 'veth9f2', 'vmnet1', 'vboxnet0'):
            self.assertTrue(self.dw._is_virtual(name), name)

    def test_real_interfaces_are_not_virtual(self):
        for name in ('eth0', 'enp8s0', 'wlo1', 'wlan0', 'tun0', 'eno1'):
            self.assertFalse(self.dw._is_virtual(name), name)

    def test_tunnels_are_recognised(self):
        for name in ('tun0', 'tap1', 'wg0', 'ppp0', 'nordlynx', 'proton0', 'zt7abc'):
            self.assertTrue(self.dw._is_tunnel(name), name)

    def test_physical_interfaces_are_not_tunnels(self):
        for name in ('eth0', 'wlo1', 'enp8s0'):
            self.assertFalse(self.dw._is_tunnel(name), name)


if __name__ == '__main__':
    unittest.main()
