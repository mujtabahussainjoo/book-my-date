from __future__ import annotations

import unittest
from datetime import date, datetime, time

from book_my_date.core.calendar_utils import (
    events_on_day,
    group_events_by_day,
    long_date,
    month_bounds,
    month_grid,
    month_title,
    normalize_week_start,
    relative_day_label,
    shift_month,
    visible_events,
    weekday_headers,
    weekend_kind,
    weekend_positions,
)
from book_my_date.core.models import Event


def local_dt(year: int, month: int, day: int, hour: int = 9) -> datetime:
    return datetime.combine(date(year, month, day), time(hour)).astimezone()


class CalendarUtilsTests(unittest.TestCase):
    def test_month_grid_is_six_weeks_and_starts_on_week_start(self) -> None:
        grid = month_grid(2024, 2, week_start=0)
        self.assertEqual(len(grid), 6)
        self.assertTrue(all(len(week) == 7 for week in grid))
        self.assertEqual(grid[0][0], date(2024, 1, 29))
        self.assertEqual(grid[-1][-1], date(2024, 3, 10))
        self.assertEqual(len({day for week in grid for day in week}), 42)

        sunday_grid = month_grid(2024, 2, week_start=1)
        self.assertEqual(sunday_grid[0][0], date(2024, 1, 28))

    def test_month_grid_rejects_bad_month(self) -> None:
        with self.assertRaises(ValueError):
            month_grid(2024, 0)
        with self.assertRaises(ValueError):
            month_grid(2024, 13)

    def test_week_headers_and_weekends(self) -> None:
        self.assertEqual(weekday_headers(0), ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"])
        self.assertEqual(weekday_headers(1), ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"])
        self.assertEqual(weekend_positions(0), {5, 6})
        self.assertEqual(weekend_positions(1), {0, 6})
        self.assertEqual(normalize_week_start(6), 6)
        self.assertEqual(normalize_week_start(1), 6)
        self.assertEqual(weekend_kind(date(2026, 5, 9)), "sat")
        self.assertEqual(weekend_kind(date(2026, 5, 10)), "sun")
        self.assertEqual(weekend_kind(date(2026, 5, 11)), "")

    def test_month_bounds_shift_and_titles(self) -> None:
        self.assertEqual(month_bounds(2024, 2), (date(2024, 2, 1), date(2024, 2, 29)))
        self.assertEqual(shift_month(2026, 12, 1), (2027, 1))
        self.assertEqual(shift_month(2026, 1, -1), (2025, 12))
        self.assertEqual(month_title(2026, 5), "May 2026")
        self.assertEqual(long_date(date(2026, 5, 4)), "Monday, 4 May 2026")

    def test_relative_day_labels(self) -> None:
        today = date(2026, 5, 4)
        self.assertEqual(relative_day_label(today, today), "Today")
        self.assertEqual(relative_day_label(date(2026, 5, 5), today), "Tomorrow")
        self.assertEqual(relative_day_label(date(2026, 5, 3), today), "Yesterday")
        self.assertEqual(relative_day_label(date(2026, 5, 7), today), "In 3 days")
        self.assertEqual(relative_day_label(date(2026, 5, 1), today), "3 days ago")
        self.assertEqual(relative_day_label(date(2026, 6, 1), today), "Mon, 1 Jun")

    def test_grouping_and_sorting_multiple_events(self) -> None:
        all_day = Event(
            "Holiday",
            local_dt(2026, 5, 4, 12),
            local_dt(2026, 5, 4, 12),
            all_day=True,
        )
        morning = Event("Standup", local_dt(2026, 5, 4, 8), local_dt(2026, 5, 4, 9))
        multi = Event("Trip", local_dt(2026, 5, 4, 18), local_dt(2026, 5, 5, 8))
        grouped = group_events_by_day([morning, multi, all_day])
        self.assertEqual(
            [event.title for event in grouped[date(2026, 5, 4)]],
            ["Holiday", "Standup", "Trip"],
        )
        self.assertEqual([event.title for event in grouped[date(2026, 5, 5)]], ["Trip"])
        self.assertEqual(
            [event.title for event in events_on_day([morning, multi], date(2026, 5, 4))],
            ["Standup", "Trip"],
        )

    def test_visible_events_returns_hidden_count(self) -> None:
        events = [
            Event(f"Event {index}", local_dt(2026, 5, 4, 8 + index), local_dt(2026, 5, 4, 9 + index))
            for index in range(5)
        ]
        shown, hidden = visible_events(events, limit=3)
        self.assertEqual([event.title for event in shown], ["Event 0", "Event 1", "Event 2"])
        self.assertEqual(hidden, 2)
        self.assertEqual(visible_events(events, limit=0), ([], 5))
        with self.assertRaises(ValueError):
            visible_events(events, limit=-1)


if __name__ == "__main__":
    unittest.main()
