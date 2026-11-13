from __future__ import annotations

import sqlite3
import tempfile
import unittest
from datetime import date, datetime, time, timedelta
from pathlib import Path

from book_my_date.core.database import Database, DatabaseError
from book_my_date.core.models import Event


def local_dt(year: int, month: int, day: int, hour: int = 9, minute: int = 0) -> datetime:
    return datetime.combine(date(year, month, day), time(hour, minute)).astimezone()


class DatabaseTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.path = Path(self.temp_dir.name) / "calendar.db"
        self.db = Database(self.path)

    def tearDown(self) -> None:
        self.db.close()
        self.temp_dir.cleanup()

    def add(
        self,
        title: str,
        start: datetime,
        end: datetime | None = None,
        **kwargs: object,
    ) -> Event:
        if end is None:
            end = start + timedelta(hours=1)
        return self.db.add_event(Event(title, start, end, **kwargs))

    def test_add_get_and_list_events(self) -> None:
        event = self.add("Planning", local_dt(2026, 5, 4, 9), local_dt(2026, 5, 4, 10))
        self.assertIsNotNone(event.id)
        self.assertEqual(event.title, "Planning")
        self.assertIsNotNone(event.created_at)
        self.assertIsNotNone(event.updated_at)
        loaded = self.db.get_event(event.id or 0)
        self.assertIsNotNone(loaded)
        assert loaded is not None
        self.assertEqual(loaded.title, "Planning")
        self.assertEqual(loaded.start_at, event.start_at)

        self.add("Later", local_dt(2026, 5, 5, 9), local_dt(2026, 5, 5, 10))
        self.add("Earlier", local_dt(2026, 5, 3, 9), local_dt(2026, 5, 3, 10))
        listed = self.db.list_events(date(2026, 5, 4), date(2026, 5, 5))
        self.assertEqual([item.title for item in listed], ["Planning", "Later"])

    def test_missing_event_lookups(self) -> None:
        self.assertIsNone(self.db.get_event(999))
        self.assertFalse(self.db.delete_event(999))
        with self.assertRaises(DatabaseError):
            self.db.update_event(Event("Missing", local_dt(2026, 5, 4), local_dt(2026, 5, 4, 10), id=999))

    def test_update_event_and_schedule_change_resets_notification(self) -> None:
        event = self.add("Planning", local_dt(2026, 5, 4, 9), local_dt(2026, 5, 4, 10))
        assert event.id is not None
        self.db.mark_notified([event.id])
        notified = self.db.get_event(event.id)
        assert notified is not None
        self.assertTrue(notified.notified)

        updated = self.db.update_event(
            notified.copy(
                title="Planning v2",
                description="Updated",
                start_at=local_dt(2026, 5, 4, 10),
                end_at=local_dt(2026, 5, 4, 11),
            )
        )
        self.assertEqual(updated.title, "Planning v2")
        self.assertFalse(updated.notified)
        self.assertEqual(updated.created_at, notified.created_at)

        refreshed = self.db.get_event(event.id)
        assert refreshed is not None
        self.assertEqual(refreshed.description, "Updated")
        self.assertFalse(refreshed.notified)

        self.db.mark_notified([event.id])
        notified_again = self.db.get_event(event.id)
        assert notified_again is not None
        renamed = self.db.update_event(notified_again.copy(title="Planning v3"))
        self.assertTrue(renamed.notified)

    def test_delete_event(self) -> None:
        event = self.add("Temporary", local_dt(2026, 5, 4, 9), local_dt(2026, 5, 4, 10))
        assert event.id is not None
        self.assertTrue(self.db.delete_event(event.id))
        self.assertIsNone(self.db.get_event(event.id))

    def test_events_for_day_and_month(self) -> None:
        self.add("May first", local_dt(2026, 5, 1, 9), local_dt(2026, 5, 1, 10))
        self.add("May last", local_dt(2026, 5, 31, 9), local_dt(2026, 5, 31, 10))
        self.add("June first", local_dt(2026, 6, 1, 9), local_dt(2026, 6, 1, 10))
        self.add("Across May", local_dt(2026, 5, 31, 22), local_dt(2026, 6, 1, 2))
        titles = [event.title for event in self.db.events_for_month(2026, 5)]
        self.assertEqual(titles, ["May first", "May last", "Across May"])
        day_titles = [event.title for event in self.db.events_for_day(date(2026, 6, 1))]
        self.assertEqual(day_titles, ["Across May", "June first"])

    def test_upcoming_events_respects_end_time(self) -> None:
        now = local_dt(2026, 5, 4, 12)
        self.add("Past", local_dt(2026, 5, 4, 9), local_dt(2026, 5, 4, 10))
        self.add("In progress", local_dt(2026, 5, 4, 11), local_dt(2026, 5, 4, 13))
        self.add("Later", local_dt(2026, 5, 5, 9), local_dt(2026, 5, 5, 10))
        titles = [event.title for event in self.db.upcoming_events(10, now=now)]
        self.assertEqual(titles, ["In progress", "Later"])
        self.assertEqual(self.db.upcoming_events(0, now=now), [])

    def test_search_escapes_sql_wildcards(self) -> None:
        self.add("100% planning", local_dt(2026, 5, 4, 9), local_dt(2026, 5, 4, 10))
        self.add("Percent planning", local_dt(2026, 5, 5, 9), local_dt(2026, 5, 5, 10))
        self.add("a_b notes", local_dt(2026, 5, 6, 9), local_dt(2026, 5, 6, 10))
        self.add("axb notes", local_dt(2026, 5, 7, 9), local_dt(2026, 5, 7, 10))

        self.assertEqual([e.title for e in self.db.search_events("%")], ["100% planning"])
        self.assertEqual([e.title for e in self.db.search_events("_")], ["a_b notes"])
        self.assertEqual(self.db.search_events(""), [])
        self.assertEqual(self.db.search_events("planning", limit=0), [])

    def test_due_reminders_mark_and_snooze(self) -> None:
        event = self.add(
            "Call",
            local_dt(2026, 5, 4, 10),
            local_dt(2026, 5, 4, 11),
            reminder_minutes=15,
        )
        assert event.id is not None
        self.assertEqual(self.db.due_reminders(local_dt(2026, 5, 4, 9, 44)), [])
        due = self.db.due_reminders(local_dt(2026, 5, 4, 9, 45))
        self.assertEqual([item.title for item in due], ["Call"])
        self.db.mark_notified([event.id])
        self.assertEqual(self.db.due_reminders(local_dt(2026, 5, 4, 9, 50)), [])

        target = self.db.snooze_reminder(
            event.id, minutes=10, now=local_dt(2026, 5, 4, 9, 46)
        )
        self.assertEqual(target, local_dt(2026, 5, 4, 9, 56))
        due_again = self.db.due_reminders(local_dt(2026, 5, 4, 9, 56))
        self.assertEqual([item.title for item in due_again], ["Call"])

    def test_snooze_rejects_non_positive_minutes(self) -> None:
        with self.assertRaises(ValueError):
            self.db.snooze_reminder(1, minutes=0)

    def test_settings(self) -> None:
        self.assertEqual(self.db.get_setting("week_start"), "0")
        self.assertTrue(self.db.get_bool("notifications"))
        self.assertEqual(self.db.get_int("default_reminder", 0), 15)
        self.db.set_setting("week_start", 1)
        self.db.set_setting("notifications", False)
        self.db.set_setting("custom", None)
        self.assertEqual(self.db.get_setting("week_start"), "1")
        self.assertFalse(self.db.get_bool("notifications"))
        self.assertEqual(self.db.get_setting("custom"), "")
        settings = self.db.all_settings()
        self.assertEqual(settings["week_start"], "1")
        self.assertIn("accent", settings)

    def test_statistics(self) -> None:
        now = local_dt(2026, 5, 4, 12)
        self.add("Today", local_dt(2026, 5, 4, 13), local_dt(2026, 5, 4, 14))
        self.add("Soon", local_dt(2026, 5, 6, 9), local_dt(2026, 5, 6, 10))
        self.add(
            "Next month",
            local_dt(2026, 6, 2, 9),
            local_dt(2026, 6, 2, 10),
            reminder_minutes=None,
        )
        stats = self.db.statistics(now=now)
        self.assertEqual(stats["total"], 3)
        self.assertEqual(stats["today"], 1)
        self.assertEqual(stats["upcoming"], 2)
        self.assertEqual(stats["this_month"], 2)
        self.assertEqual(stats["reminders"], 2)

    def test_backup_is_readable(self) -> None:
        self.add("Backup me", local_dt(2026, 5, 4, 9), local_dt(2026, 5, 4, 10))
        target = Path(self.temp_dir.name) / "backups" / "snapshot.db"
        result = self.db.backup(target)
        self.assertEqual(result, target)
        self.assertTrue(target.exists())
        connection = sqlite3.connect(str(target))
        try:
            count = connection.execute("SELECT COUNT(*) FROM events").fetchone()[0]
        finally:
            connection.close()
        self.assertEqual(count, 1)

    def test_context_manager_closes_database(self) -> None:
        path = Path(self.temp_dir.name) / "context.db"
        with Database(path) as database:
            database.add_event(Event("One", local_dt(2026, 5, 4), local_dt(2026, 5, 4, 10)))
        with self.assertRaises(sqlite3.ProgrammingError):
            database._conn.execute("SELECT 1")


if __name__ == "__main__":
    unittest.main()
