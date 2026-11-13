from __future__ import annotations

import unittest
from datetime import date, datetime, time

from book_my_date.core.models import (
    CATEGORIES,
    Event,
    ValidationError,
    category_for,
    reminder_label,
)


def local_dt(year: int, month: int, day: int, hour: int = 9, minute: int = 0) -> datetime:
    return datetime.combine(date(year, month, day), time(hour, minute)).astimezone()


class EventModelTests(unittest.TestCase):
    def test_event_strips_text_and_keeps_defaults(self) -> None:
        event = Event(
            title="  Dentist  ",
            description="  check-up  ",
            location="  Main Street  ",
            start_at=local_dt(2026, 5, 4),
            end_at=local_dt(2026, 5, 4, 10),
        )
        self.assertEqual(event.title, "Dentist")
        self.assertEqual(event.description, "check-up")
        self.assertEqual(event.location, "Main Street")
        self.assertEqual(event.category, "personal")
        self.assertFalse(event.all_day)

    def test_validation_rejects_missing_and_oversized_values(self) -> None:
        with self.assertRaises(ValidationError):
            Event("", local_dt(2026, 5, 4), local_dt(2026, 5, 4, 10))
        with self.assertRaises(ValidationError):
            Event("x" * 121, local_dt(2026, 5, 4), local_dt(2026, 5, 4, 10))
        with self.assertRaises(ValidationError):
            Event(
                "Meeting",
                local_dt(2026, 5, 4),
                local_dt(2026, 5, 4, 10),
                category="unknown",
            )
        with self.assertRaises(ValidationError):
            Event(
                "Meeting",
                local_dt(2026, 5, 4),
                local_dt(2026, 5, 4, 10),
                reminder_minutes=-1,
            )

    def test_timed_event_requires_positive_duration(self) -> None:
        with self.assertRaises(ValidationError):
            Event("Meeting", local_dt(2026, 5, 4, 10), local_dt(2026, 5, 4, 10))
        with self.assertRaises(ValidationError):
            Event("Meeting", local_dt(2026, 5, 4, 10), local_dt(2026, 5, 4, 9))

    def test_all_day_event_normalizes_to_full_days(self) -> None:
        event = Event(
            "Conference",
            local_dt(2026, 5, 4, 13),
            local_dt(2026, 5, 6, 11),
            all_day=True,
        )
        self.assertEqual(event.start_at.time(), time.min)
        self.assertEqual(event.end_at.time(), time(23, 59, 59))
        self.assertEqual(event.duration_minutes, 3)
        self.assertTrue(event.occurs_on(date(2026, 5, 5)))
        self.assertEqual(event.display_time_range(), "All day · 3 days")

    def test_reminder_times_and_labels(self) -> None:
        event = Event(
            "Dinner",
            local_dt(2026, 5, 4, 19),
            local_dt(2026, 5, 4, 21),
            reminder_minutes=30,
        )
        self.assertEqual(event.reminder_at, local_dt(2026, 5, 4, 18, 30))
        self.assertEqual(reminder_label(30), "30 minutes before")
        self.assertEqual(reminder_label(120), "2 hours before")
        self.assertEqual(reminder_label(2880), "2 days before")
        self.assertEqual(reminder_label(None), "No reminder")

        all_day = Event(
            "Birthday",
            local_dt(2026, 5, 4, 12),
            local_dt(2026, 5, 4, 12),
            all_day=True,
            reminder_minutes=15,
        )
        self.assertEqual(all_day.reminder_at, local_dt(2026, 5, 4, 8, 45))

    def test_display_and_notification_copy(self) -> None:
        event = Event(
            "Planning",
            local_dt(2026, 5, 4, 9),
            local_dt(2026, 5, 4, 10, 30),
            location="Studio",
            description="Roadmap " * 40,
        )
        self.assertEqual(event.display_time_range(), "09:00 – 10:30")
        self.assertEqual(event.notification_body(), "09:00 – 10:30 · Studio")
        self.assertTrue(event.short_description(40).endswith("…"))
        self.assertLessEqual(len(event.short_description(40)), 40)

    def test_category_lookup_and_copy(self) -> None:
        self.assertEqual(category_for("work"), CATEGORIES["work"])
        self.assertEqual(category_for("missing"), CATEGORIES["personal"])
        event = Event("One", local_dt(2026, 5, 4), local_dt(2026, 5, 4, 10))
        changed = event.copy(title="Two")
        self.assertEqual(changed.title, "Two")
        self.assertEqual(event.title, "One")
        self.assertNotEqual(changed, event)

    def test_multi_day_timed_event_occurs_on_each_day(self) -> None:
        event = Event(
            "Trip",
            local_dt(2026, 5, 4, 18),
            local_dt(2026, 5, 6, 8),
        )
        self.assertTrue(event.occurs_on(date(2026, 5, 4)))
        self.assertTrue(event.occurs_on(date(2026, 5, 5)))
        self.assertTrue(event.occurs_on(date(2026, 5, 6)))
        self.assertFalse(event.occurs_on(date(2026, 5, 7)))
        self.assertEqual(event.duration_minutes, 38 * 60)

    def test_is_past_uses_end_time(self) -> None:
        event = Event("Call", local_dt(2026, 5, 4, 9), local_dt(2026, 5, 4, 10))
        self.assertTrue(event.is_past(local_dt(2026, 5, 4, 10, 1)))
        self.assertFalse(event.is_past(local_dt(2026, 5, 4, 9, 30)))


if __name__ == "__main__":
    unittest.main()
