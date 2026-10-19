import unittest
from diagnostics import battery_values, summarize, collect


class DiagnosticsTests(unittest.TestCase):
    def test_battery_and_thresholds(self):
        battery = battery_values('Current Battery Service state:\n  level: 70\n  temperature: 470\n  health: 3')
        self.assertEqual(battery['level'], '70')
        self.assertEqual(len(summarize(battery, 'MemTotal: 1000 kB\nMemAvailable: 50 kB', '/data 95%')), 4)

    def test_missing_values_not_claimed_healthy(self):
        result = summarize({}, '', '')
        self.assertIn('القراءات المتاحة', result[0])

    def test_partial_failure_retained(self):
        class FakeADB:
            def shell(self, serial, *args):
                if args[0] == 'dumpsys':
                    raise RuntimeError('permission denied')
                return 'test'
        report = collect(FakeADB(), 'test-device')
        self.assertEqual(len(report['errors']), 2)
        self.assertEqual(report['battery'], {})


if __name__ == '__main__':
    unittest.main()
