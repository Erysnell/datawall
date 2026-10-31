"""parse_ss_output — the per-socket byte attribution parser.

The fixture below is trimmed from real `ss -tpin` output and keeps the cases
that matter: sockets with an owning process, sockets without one (which is
where unattributed traffic comes from), a state line whose detail line is
blank, and the column header.
"""
import unittest

from helpers import IsolatedHomeTest

HEADER = ('State      Recv-Q Send-Q  Local Address:Port     '
          'Peer Address:PortProcess')

# socket with an owner and both byte counters
OWNED = (
    'ESTAB      0      0          10.98.0.10:46754 162.159.140.220:443  '
    'users:(("curl",pid=7495,fd=5))\n'
    '\t cubic wscale:10,7 rto:528 rtt:182.734/62.385 mss:1348 '
    'bytes_sent:723 bytes_acked:724 bytes_received:573874 segs_out:227\n'
)
# real traffic the kernel will not attribute: no users:(( ... )) at all
UNOWNED = (
    'ESTAB      0      78     192.168.248.63:52456  149.34.251.136:8443\n'
    '\t cubic wscale:10,7 rto:1133 bytes_sent:69524298 bytes_acked:68236526 '
    'bytes_received:124035117 segs_out:181498\n'
)
# closing socket whose detail line carries nothing
BLANK_DETAIL = (
    'FIN-WAIT-2 0      0          10.98.0.10:34030  74.125.137.188:5228\n'
    '\t                              \n'
)
SECOND_OWNED = (
    'ESTAB      0      0          10.98.0.10:37370   160.79.104.10:443  '
    'users:(("claude",pid=4201,fd=11))\n'
    '\t cubic bytes_sent:3402029 bytes_acked:3397986 bytes_received:45645\n'
)
# both ends on loopback: local-only traffic the daemon must ignore
LOOPBACK = (
    'ESTAB      0      0           127.0.0.1:38402       127.0.0.1:5432  '
    'users:(("psql",pid=999,fd=3))\n'
    '\t cubic bytes_acked:5000 bytes_received:9000\n'
)
# owner known but the kernel reported no byte counters yet
NO_COUNTERS = (
    'SYN-SENT   0      1          10.98.0.10:51000     1.1.1.1:443  '
    'users:(("firefox",pid=321,fd=77))\n'
    '\t cubic rto:1000 mss:1348\n'
)


class TestParseSsOutput(IsolatedHomeTest):
    def parse(self, text, **kw):
        return self.dw.parse_ss_output(text, **kw)

    def test_owned_socket_yields_pid_fd_name_and_counters(self):
        rows = self.parse(HEADER + '\n' + OWNED)
        self.assertEqual(rows, [(7495, 5, 'curl', 724, 573874)])

    def test_header_alone_yields_nothing(self):
        self.assertEqual(self.parse(HEADER), [])

    def test_empty_input_yields_nothing(self):
        self.assertEqual(self.parse(''), [])

    def test_socket_without_an_owner_is_skipped(self):
        """This is exactly the traffic that ends up in `unattributed`."""
        self.assertEqual(self.parse(HEADER + '\n' + UNOWNED), [])

    def test_blank_detail_line_is_skipped(self):
        self.assertEqual(self.parse(HEADER + '\n' + BLANK_DETAIL), [])

    def test_loopback_to_loopback_is_skipped(self):
        self.assertEqual(self.parse(LOOPBACK), [])

    def test_owner_without_counters_is_skipped(self):
        self.assertEqual(self.parse(NO_COUNTERS), [])

    def test_mixed_output_keeps_only_attributable_sockets(self):
        rows = self.parse(HEADER + '\n' + OWNED + UNOWNED + BLANK_DETAIL +
                          SECOND_OWNED + LOOPBACK + NO_COUNTERS)
        self.assertEqual(rows, [
            (7495, 5, 'curl', 724, 573874),
            (4201, 11, 'claude', 3397986, 45645),
        ])

    def test_an_unowned_socket_does_not_leak_into_the_next_one(self):
        """Regression: `current` must be cleared between sockets."""
        rows = self.parse(HEADER + '\n' + UNOWNED + SECOND_OWNED)
        self.assertEqual(rows, [(4201, 11, 'claude', 3397986, 45645)])


class TestParseSsWithRemote(IsolatedHomeTest):
    """include_remote=True powers `datawall connections`."""

    def test_remote_address_is_returned(self):
        rows = self.dw.parse_ss_output(HEADER + '\n' + OWNED, include_remote=True)
        self.assertEqual(rows, [(7495, 5, 'curl', '162.159.140.220:443', 724, 573874)])

    def test_tuple_is_one_field_wider_than_the_default_mode(self):
        plain = self.dw.parse_ss_output(OWNED)
        with_remote = self.dw.parse_ss_output(OWNED, include_remote=True)
        self.assertEqual(len(with_remote[0]), len(plain[0]) + 1)

    def test_unowned_sockets_are_still_skipped(self):
        self.assertEqual(self.dw.parse_ss_output(UNOWNED, include_remote=True), [])


if __name__ == '__main__':
    unittest.main()
