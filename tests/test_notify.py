"""Daily-limit notification thresholds.

send_notification is replaced so nothing reaches the desktop and delivery
failure can be simulated.
"""
import unittest

from helpers import IsolatedHomeTest

LIMIT = 1000
THRESHOLDS = [80, 100]
_UNSET = object()


class NotifyTest(IsolatedHomeTest):
    def setUp(self):
        super().setUp()
        self.sent = []
        self.deliver = True

        def fake_send(title, body, urgency='normal'):
            self.sent.append({'title': title, 'body': body, 'urgency': urgency})
            return self.deliver

        self.dw.send_notification = fake_send

    def alert(self, day, limit=LIMIT, thresholds=_UNSET, failed=None):
        # `thresholds or THRESHOLDS` would turn an explicit [] into the
        # default, so distinguish "not passed" from "passed empty"
        self.dw.check_limit_alerts(
            day, limit, THRESHOLDS if thresholds is _UNSET else thresholds,
            failed if failed is not None else set())

    @staticmethod
    def day(total):
        return {'total_sent': 0, 'total_recv': total}


class TestThresholdCrossing(NotifyTest):
    def test_below_every_threshold_is_silent(self):
        day = self.day(600)                     # 60%
        self.alert(day)
        self.assertEqual(self.sent, [])
        self.assertEqual(day.get('notified', []), [])

    def test_crossing_the_first_threshold_fires_once(self):
        day = self.day(850)                     # 85%
        self.alert(day)
        self.assertEqual(len(self.sent), 1)
        self.assertEqual(day['notified'], [80])

    def test_the_same_threshold_does_not_fire_again(self):
        day = self.day(850)
        self.alert(day)
        self.sent.clear()
        self.alert(day)
        self.assertEqual(self.sent, [])

    def test_crossing_the_next_threshold_fires_it(self):
        day = self.day(850)
        self.alert(day)
        self.sent.clear()
        day['total_recv'] = 1300                # 130%
        self.alert(day)
        self.assertEqual(len(self.sent), 1)
        self.assertEqual(day['notified'], [80, 100])

    def test_jumping_past_several_thresholds_fires_all_of_them(self):
        day = self.day(5000)                    # 500%, nothing fired yet
        self.alert(day)
        self.assertEqual(len(self.sent), 2)
        self.assertEqual(day['notified'], [80, 100])

    def test_exactly_on_the_threshold_counts_as_crossed(self):
        day = self.day(800)                     # exactly 80%
        self.alert(day)
        self.assertEqual(day['notified'], [80])

    def test_custom_thresholds_are_honoured(self):
        day = self.day(550)
        self.alert(day, thresholds=[25, 50, 75])
        self.assertEqual(day['notified'], [25, 50])


class TestMessageContent(NotifyTest):
    def test_sub_limit_alert_uses_normal_urgency(self):
        self.alert(self.day(850))
        self.assertEqual(self.sent[0]['urgency'], 'normal')
        self.assertIn('80%', self.sent[0]['title'])

    def test_exceeding_the_limit_uses_critical_urgency(self):
        self.alert(self.day(1300))
        exceeded = [s for s in self.sent if s['urgency'] == 'critical']
        self.assertEqual(len(exceeded), 1)
        self.assertIn('exceeded', exceeded[0]['title'])

    def test_body_reports_usage_limit_and_percentage(self):
        self.alert(self.day(1300))
        body = self.sent[-1]['body']
        self.assertIn('1.3 KB', body)
        self.assertIn('1000.0 B', body)
        self.assertIn('130%', body)


class TestDeliveryFailure(NotifyTest):
    def test_a_failed_send_is_not_marked_as_fired(self):
        self.deliver = False
        day = self.day(850)
        failed = set()
        self.alert(day, failed=failed)
        self.assertEqual(day.get('notified', []), [])
        self.assertEqual(failed, {80})

    def test_it_is_retried_and_marked_once_delivery_works(self):
        self.deliver = False
        day = self.day(850)
        failed = set()
        self.alert(day, failed=failed)
        self.deliver = True
        self.sent.clear()
        self.alert(day, failed=failed)
        self.assertEqual(len(self.sent), 1)
        self.assertEqual(day['notified'], [80])
        self.assertEqual(failed, set())

    def test_repeated_failures_are_only_recorded_once(self):
        self.deliver = False
        day = self.day(850)
        failed = set()
        for _ in range(3):
            self.alert(day, failed=failed)
        self.assertEqual(failed, {80})


class TestNoAlertCases(NotifyTest):
    def test_no_limit_configured(self):
        self.alert(self.day(999999), limit=None)
        self.assertEqual(self.sent, [])

    def test_zero_limit(self):
        self.alert(self.day(999999), limit=0)
        self.assertEqual(self.sent, [])

    def test_zero_traffic(self):
        self.alert(self.day(0))
        self.assertEqual(self.sent, [])

    def test_an_empty_threshold_list(self):
        self.alert(self.day(5000), thresholds=[])
        self.assertEqual(self.sent, [])


class TestNotifyAvailability(IsolatedHomeTest):
    def test_availability_probe_returns_a_bool(self):
        self.assertIsInstance(self.dw.notify_available(), bool)

    def test_a_missing_binary_is_reported_as_unavailable(self):
        self.dw.shutil.which = lambda _name: None
        self.assertFalse(self.dw.notify_available())

    def test_send_reports_failure_when_the_binary_is_missing(self):
        def boom(*_a, **_kw):
            raise FileNotFoundError('notify-send')
        self.dw.subprocess.run = boom
        self.assertFalse(self.dw.send_notification('t', 'b'))


if __name__ == '__main__':
    unittest.main()
