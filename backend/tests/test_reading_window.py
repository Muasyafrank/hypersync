import unittest
from datetime import date

from app.core.reading_window import ReadingWindow, days_ago, format_span


class FormatSpan(unittest.TestCase):
    def test_same_month(self):
        self.assertEqual(format_span(date(2026, 9, 23), date(2026, 9, 28)), "Sep 23\u201328")

    def test_single_day(self):
        self.assertEqual(format_span(date(2026, 9, 28), date(2026, 9, 28)), "Sep 28")

    def test_across_months(self):
        self.assertEqual(format_span(date(2026, 9, 28), date(2026, 10, 2)), "Sep 28 \u2013 Oct 2")


class Window(unittest.TestCase):
    def test_fresh_window_reads_as_before(self):
        w = ReadingWindow(period_days=7)
        self.assertEqual(w.phrase, "over the last 7 days")
        self.assertEqual(w.nudge, "")
        self.assertFalse(w.is_stale)

    def test_stale_window_names_the_dates_and_nudges(self):
        w = ReadingWindow(7, stale_days=18, first_day=date(2026, 9, 23), last_day=date(2026, 9, 28))
        self.assertIn("most recent readings (Sep 23\u201328)", w.phrase)
        self.assertIn("18 days ago", w.nudge)
        self.assertEqual(w.period_label, "that period")

    def test_days_ago(self):
        self.assertEqual(days_ago(1), "1 day ago")
        self.assertEqual(days_ago(0), "today")


if __name__ == "__main__":
    unittest.main()
