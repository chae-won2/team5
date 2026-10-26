import unittest
from unittest.mock import patch
import pandas as pd

from app.services import opening_hours as oh


def row(place_id, weekday, status, opens_at="", closes_at="", closes_next_day=""):
    return dict(place_id=place_id, weekday=weekday, status=status, opens_at=opens_at,
                closes_at=closes_at, closes_next_day=closes_next_day, source="test", checked_date="2026-10-26")


class OpeningHoursTests(unittest.TestCase):
    def frame(self, rows):
        return pd.DataFrame(rows)

    def status(self, rows, place_id, weekday, minutes):
        oh._index.cache_clear()
        with patch("app.services.opening_hours.load_opening_hours", return_value=self.frame(rows)):
            return oh.status_at(place_id, weekday, minutes)

    def test_open_within_same_day_window(self):
        rows = [row("a", 0, "open", "09:00", "18:00", 0)]
        self.assertEqual(self.status(rows, "a", 0, 9 * 60), "open")
        self.assertEqual(self.status(rows, "a", 0, 17 * 60 + 59), "open")
        self.assertEqual(self.status(rows, "a", 0, 18 * 60), "unknown")
        self.assertEqual(self.status(rows, "a", 0, 8 * 60 + 59), "unknown")

    def test_closes_next_day_same_day_and_carryover(self):
        rows = [row("a", 4, "open", "18:00", "02:00", 1)]
        self.assertEqual(self.status(rows, "a", 4, 23 * 60), "open")
        self.assertEqual(self.status(rows, "a", 5, 1 * 60), "open")
        self.assertEqual(self.status(rows, "a", 5, 2 * 60), "unknown")
        self.assertEqual(self.status(rows, "a", 4, 17 * 60), "unknown")

    def test_sunday_to_monday_wraps_weekday_correctly(self):
        rows = [row("a", 6, "open", "22:00", "01:00", 1)]
        self.assertEqual(self.status(rows, "a", 0, 0), "open")
        self.assertEqual(self.status(rows, "a", 0, 59), "open")
        self.assertEqual(self.status(rows, "a", 0, 60), "unknown")

    def test_closed_day_is_reported_closed_not_unknown(self):
        rows = [row("a", 1, "closed")]
        self.assertEqual(self.status(rows, "a", 1, 12 * 60), "closed")

    def test_day_with_no_record_is_unknown_even_if_other_days_exist(self):
        rows = [row("a", 0, "open", "09:00", "18:00", 0)]
        self.assertEqual(self.status(rows, "a", 2, 12 * 60), "unknown")

    def test_unrelated_place_does_not_leak(self):
        rows = [row("a", 0, "open", "09:00", "18:00", 0)]
        self.assertEqual(self.status(rows, "b", 0, 12 * 60), "unknown")

    def test_resolve_context_defaults_to_now_when_omitted(self):
        with patch("app.services.opening_hours.datetime") as mock_dt:
            from datetime import datetime, date
            mock_dt.now.return_value = datetime(2026, 10, 26, 14, 5)
            mock_dt.strptime = datetime.strptime
            self.assertEqual(oh.resolve_context(None, None), (0, 14 * 60 + 5))
            self.assertEqual(oh.resolve_context("2026-10-27", None), (1, 14 * 60 + 5))
            self.assertEqual(oh.resolve_context(None, "09:30"), (0, 9 * 60 + 30))

    def test_resolve_context_rejects_invalid_date(self):
        with self.assertRaises(ValueError):
            oh.resolve_context("2026-02-30", None)


if __name__ == "__main__":
    unittest.main()
