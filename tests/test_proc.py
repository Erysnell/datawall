"""Parsers for the /proc/net files, driven by fixtures rather than the host."""
import os
import unittest

from helpers import IsolatedHomeTest

ROUTE = """Iface\tDestination\tGateway \tFlags\tRefCnt\tUse\tMetric\tMask\t\tMTU\tWindow\tIRTT
wlo1\t00F8A8C0\t00000000\t0001\t0\t0\t600\t00FFFFFF\t0\t0\t0
tun0\t00000000\t0162A80A\t0003\t0\t0\t50\t00000000\t0\t0\t0
wlo1\t00000000\t01F8A8C0\t0003\t0\t0\t600\t00000000\t0\t0\t0
"""
ROUTE_NO_DEFAULT = """Iface\tDestination\tGateway \tFlags\tRefCnt\tUse\tMetric\tMask\t\tMTU\tWindow\tIRTT
wlo1\t00F8A8C0\t00000000\t0001\t0\t0\t600\t00FFFFFF\t0\t0\t0
"""
SNMP = """Tcp: RtoAlgorithm RtoMin MaxConn InSegs OutSegs RetransSegs
Tcp: 1 200 -1 1120896 1468056 5361
Udp: InDatagrams NoPorts InErrors OutDatagrams
Udp: 186911 1030 3388 78800
"""
NETSTAT = """IpExt: InNoRoutes InTruncatedPkts InOctets OutOctets
IpExt: 0 0 878797736 1386075687
"""


class TestDefaultRouteIface(IsolatedHomeTest):
    def write(self, name, text):
        path = os.path.join(self.home, name)
        with open(path, 'w') as f:
            f.write(text)
        return path

    def test_returns_the_interface_of_the_default_route(self):
        """Destination 00000000 marks the default route; the first wins."""
        self.assertEqual(self.dw._default_route_iface(self.write('route', ROUTE)), 'tun0')

    def test_returns_none_without_a_default_route(self):
        self.assertIsNone(self.dw._default_route_iface(self.write('r2', ROUTE_NO_DEFAULT)))

    def test_returns_none_for_a_missing_file(self):
        self.assertIsNone(self.dw._default_route_iface(os.path.join(self.home, 'nope')))

    def test_returns_none_for_a_header_only_file(self):
        self.assertIsNone(self.dw._default_route_iface(self.write('r3', 'Iface\tDestination\n')))

    def test_returns_none_for_an_empty_file(self):
        self.assertIsNone(self.dw._default_route_iface(self.write('r4', '')))


class TestReadProcCounters(IsolatedHomeTest):
    def setUp(self):
        super().setUp()
        self.snmp = os.path.join(self.home, 'snmp')
        self.netstat = os.path.join(self.home, 'netstat')
        with open(self.snmp, 'w') as f:
            f.write(SNMP)
        with open(self.netstat, 'w') as f:
            f.write(NETSTAT)

    def read(self, paths=None):
        return self.dw._read_proc_counters(paths or (self.snmp, self.netstat))

    def test_pairs_header_names_with_their_values(self):
        c = self.read()
        self.assertEqual(c['Tcp.InSegs'], 1120896)
        self.assertEqual(c['Tcp.OutSegs'], 1468056)
        self.assertEqual(c['Udp.InDatagrams'], 186911)
        self.assertEqual(c['Udp.OutDatagrams'], 78800)
        self.assertEqual(c['IpExt.InOctets'], 878797736)
        self.assertEqual(c['IpExt.OutOctets'], 1386075687)

    def test_only_the_requested_fields_are_returned(self):
        self.assertNotIn('Tcp.RtoAlgorithm', self.read())

    def test_missing_files_are_skipped_without_raising(self):
        self.assertEqual(self.dw._read_proc_counters((os.path.join(self.home, 'absent'),)), {})

    def test_a_truncated_value_row_does_not_raise(self):
        path = os.path.join(self.home, 'short')
        with open(path, 'w') as f:
            f.write('Tcp: RtoAlgorithm InSegs OutSegs\nTcp: 1\n')
        self.assertEqual(self.dw._read_proc_counters((path,)), {})

    def test_non_numeric_values_are_dropped(self):
        path = os.path.join(self.home, 'bad')
        with open(path, 'w') as f:
            f.write('Tcp: InSegs OutSegs\nTcp: abc 42\n')
        c = self.dw._read_proc_counters((path,))
        self.assertNotIn('Tcp.InSegs', c)
        self.assertEqual(c['Tcp.OutSegs'], 42)

    def test_reads_the_real_files_on_this_host(self):
        """Smoke test: the live format must still match what we parse."""
        c = self.dw._read_proc_counters()
        for key in ('Tcp.InSegs', 'Tcp.OutSegs', 'Udp.InDatagrams',
                    'Udp.OutDatagrams', 'IpExt.InOctets', 'IpExt.OutOctets'):
            self.assertIn(key, c, f'{key} missing — /proc format may have changed')
            self.assertIsInstance(c[key], int)


class TestSocketOwnership(IsolatedHomeTest):
    def test_returns_two_counts_with_unowned_never_exceeding_total(self):
        unowned, total = self.dw._socket_ownership()
        self.assertGreaterEqual(total, 0)
        self.assertLessEqual(unowned, total)

    def test_reports_zeroes_when_ss_is_absent(self):
        def boom(*_a, **_kw):
            raise FileNotFoundError('ss')
        self.dw.subprocess.run = boom
        self.assertEqual(self.dw._socket_ownership(), (0, 0))


if __name__ == '__main__':
    unittest.main()
