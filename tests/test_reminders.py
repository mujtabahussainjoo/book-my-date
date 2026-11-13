from __future__ import annotations

import tempfile
import unittest
from datetime import date, datetime, time
from pathlib import Path

from book_my_date.core.database import Database
from book_my_date.core.models import Event
from book_my_date.core.reminders import ReminderEngine


def local_dt(year: int, month: int, day: int, hour: int = 9, minute: int = 0) -> datetime:
    return datetime.combine(date(year, month, day), time(hour, minute)).astimezone()


class ReminderEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db = Database(Path(self.temp_dir.name) / "calendar.db")
        self.now = local_dt(2026, 5, 4, 9, 44)
        self.engine = ReminderEngine(self.db, clock=lambda: self.now)
        self.event = self.db.add_event(
            Event(
                "Call",
                local_dt(2026, 5, 4, 10),
                local_dt(2026, 5, 4, 11),
                reminder_minutes=15,
            )
        )

    def tearDown(self) -> None:
        self.db.close()
        self.temp_dir.cleanup()

    def test_pop_due_returns_event_only_once(self) -> None:
        self.assertEqual(self.engine.pop_due(), [])
        self.now = local_dt(2026, 5, 4, 9, 45)
        self.assertEqual([event.title for event in self.engine.pop_due()], ["Call"])
        self.assertEqual(self.engine.pop_due(), [])
        loaded = self.db.get_event(self.event.id or 0)
        assert loaded is not None
        self.assertTrue(loaded.notified)

    def test_snooze_reschedules_reminder(self) -> None:
        self.now = local_dt(2026, 5, 4, 9, 46)
        target = self.engine.snooze(self.event, minutes=10)
        self.assertEqual(target, local_dt(2026, 5, 4, 9, 56))
        self.assertEqual(self.engine.pop_due(), [])
        self.now = local_dt(2026, 5, 4, 9, 56)
        self.assertEqual([event.title for event in self.engine.pop_due()], ["Call"])

    def test_snooze_unsaved_event_returns_none(self) -> None:
        unsaved = Event("Unsaved", local_dt(2026, 5, 4, 10), local_dt(2026, 5, 4, 11))
        self.assertIsNone(self.engine.snooze(unsaved))

    def test_event_without_reminder_never_appears(self) -> None:
        self.db.add_event(
            Event(
                "No reminder",
                local_dt(2026, 5, 4, 10),
                local_dt(2026, 5, 4, 11),
                reminder_minutes=None,
            )
        )
        self.now = local_dt(2026, 5, 4, 12)
        self.assertEqual(self.engine.pop_due(), [])

    def test_past_event_is_not_returned(self) -> None:
        self.now = local_dt(2026, 5, 4, 11, 1)
        self.assertEqual(self.engine.pop_due(), [])


if __name__ == "__main__":
    unittest.main()
