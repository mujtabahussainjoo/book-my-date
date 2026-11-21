from __future__ import annotations

import os
import sqlite3
import tempfile
import unittest
from datetime import date
from pathlib import Path

from PySide6.QtWidgets import QApplication

from book_my_date.core.database import Database, DatabaseError
from book_my_date.core.models import (
    Subtask,
    TaskTopic,
    ValidationError,
    nearest_status,
)
from book_my_date.core.reminders import ReminderEngine
from book_my_date.ui.main_window import MainWindow
from book_my_date.ui.task_widgets import SubtaskRow, TaskTopicCard


def topic(**changes: object) -> TaskTopic:
    defaults: dict[str, object] = {
        "title": "Morning routine",
        "subtasks": [Subtask("Water"), Subtask("Walk", "emerald")],
    }
    defaults.update(changes)
    return TaskTopic(**defaults)  # type: ignore[arg-type]


class TaskModelTests(unittest.TestCase):
    def test_validation(self) -> None:
        with self.assertRaises(ValidationError):
            TaskTopic(" ", [Subtask("One")])
        with self.assertRaises(ValidationError):
            topic(subtasks=[Subtask(" ")])
        with self.assertRaises(ValidationError):
            topic(subtasks=[Subtask("One", "unknown-color")])
        with self.assertRaises(ValidationError):
            topic(apply_to_all_dates=False, weekdays=frozenset())
        with self.assertRaises(ValidationError):
            topic(
                apply_to_all_dates=False,
                start_date=date(2026, 5, 10),
                end_date=date(2026, 5, 9),
            )
        with self.assertRaises(ValidationError):
            topic(progress={1: 60})

    def test_applies_on_respects_range_and_weekdays(self) -> None:
        every_day = topic()
        self.assertTrue(every_day.applies_on(date(2001, 1, 1)))

        limited = topic(
            apply_to_all_dates=False,
            start_date=date(2026, 5, 4),
            end_date=date(2026, 5, 10),
            weekdays=frozenset({0, 2}),
        )
        self.assertTrue(limited.applies_on(date(2026, 5, 4)))
        self.assertTrue(limited.applies_on(date(2026, 5, 6)))
        self.assertFalse(limited.applies_on(date(2026, 5, 5)))
        self.assertFalse(limited.applies_on(date(2026, 5, 12)))
        self.assertFalse(limited.applies_on(date(2026, 5, 1)))

    def test_progress_and_completion(self) -> None:
        item = topic()
        item.subtasks[0].id = 1
        item.subtasks[1].id = 2
        item.progress = {1: 100, 2: 75}
        self.assertEqual(item.status_for(1), 100)
        self.assertEqual(item.status_for(999), 0)
        self.assertEqual(item.completion(), 88)
        self.assertEqual(item.completed_count(), 1)
        self.assertEqual(nearest_status(88), 100)
        self.assertEqual(nearest_status(40), 50)
        self.assertEqual(topic(subtasks=[]).completion(), 0)

    def test_manual_completion_override_is_per_date(self) -> None:
        day = date(2026, 5, 4)
        item = topic()
        item.manual_progress[day] = 42
        self.assertEqual(item.completion_for(day), 42)
        self.assertEqual(item.completion_for(date(2026, 5, 5)), 0)
        self.assertTrue(item.has_manual_progress(day))
        self.assertEqual(item.copy().completion_for(day), 42)
        with self.assertRaises(ValidationError):
            topic(manual_progress={day: 101})


class TaskDatabaseTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.path = Path(self.temp_dir.name) / "tasks.db"
        self.db = Database(self.path)

    def tearDown(self) -> None:
        self.db.close()
        self.temp_dir.cleanup()

    def test_add_get_and_list_topics(self) -> None:
        saved = self.db.add_topic(topic())
        self.assertIsNotNone(saved.id)
        self.assertEqual([child.id for child in saved.subtasks if child.id], [1, 2])
        self.assertIsNotNone(saved.created_at)
        loaded = self.db.get_topic(saved.id or 0)
        assert loaded is not None
        self.assertEqual(loaded.title, "Morning routine")
        self.assertTrue(loaded.apply_to_all_dates)
        self.assertEqual([child.title for child in loaded.subtasks], ["Water", "Walk"])
        self.assertEqual([item.id for item in self.db.list_topics()], [saved.id])

    def test_update_syncs_subtasks_and_keeps_progress(self) -> None:
        saved = self.db.add_topic(topic())
        assert saved.id is not None
        first_id = saved.subtasks[0].id
        assert first_id is not None
        day = date(2026, 5, 4)
        self.db.set_subtask_progress(first_id, day, 75)

        saved.title = "Daily routine"
        saved.subtasks[1].title = "Stretch"
        saved.subtasks.append(Subtask("Read", "violet"))
        self.db.update_topic(saved)

        loaded = self.db.get_topic(saved.id)
        assert loaded is not None
        self.assertEqual(loaded.title, "Daily routine")
        self.assertEqual(
            [child.title for child in loaded.subtasks], ["Water", "Stretch", "Read"]
        )
        self.assertEqual(
            [child.id for child in loaded.subtasks[:2]], [first_id, loaded.subtasks[1].id]
        )

        for item in self.db.topics_for_day(day):
            self.assertEqual(item.status_for(first_id), 75)

    def test_daily_progress_is_independent_per_date(self) -> None:
        saved = self.db.add_topic(topic())
        first, second = saved.subtasks
        assert first.id is not None and second.id is not None
        self.db.set_subtask_progress(first.id, date(2026, 5, 4), 100)
        self.db.set_subtask_progress(second.id, date(2026, 5, 4), 100)
        self.db.set_subtask_progress(first.id, date(2026, 5, 4), 25)

        may_fourth = self.db.topics_for_day(date(2026, 5, 4))
        may_fifth = self.db.topics_for_day(date(2026, 5, 5))
        self.assertEqual(may_fourth[0].status_for(first.id), 25)
        self.assertEqual(may_fourth[0].status_for(second.id), 100)
        self.assertEqual(may_fourth[0].completion(), 63)
        self.assertEqual(may_fifth[0].completion(), 0)

    def test_manual_topic_progress_is_stored_per_date(self) -> None:
        saved = self.db.add_topic(topic())
        assert saved.id is not None
        day = date(2026, 5, 4)
        self.db.set_topic_progress(saved.id, day, 42)
        self.assertEqual(self.db.topics_for_day(day)[0].completion_for(day), 42)
        other = date(2026, 5, 5)
        self.assertEqual(self.db.topics_for_day(other)[0].completion_for(other), 0)
        self.db.clear_topic_progress(saved.id, day)
        self.assertEqual(self.db.topics_for_day(day)[0].completion_for(day), 0)
        with self.assertRaises(ValidationError):
            self.db.set_topic_progress(saved.id, day, 101)

    def test_topics_by_day_and_schedule_filtering(self) -> None:
        self.db.add_topic(topic())
        weekday_topic = topic(
            title="Monday only",
            apply_to_all_dates=False,
            start_date=date(2026, 5, 4),
            end_date=date(2026, 5, 11),
            weekdays=frozenset({0}),
        )
        self.db.add_topic(weekday_topic)
        by_day = self.db.topics_by_day(date(2026, 5, 3), date(2026, 5, 12))
        self.assertEqual(len(by_day[date(2026, 5, 3)]), 1)
        self.assertEqual(len(by_day[date(2026, 5, 4)]), 2)
        self.assertEqual(
            [item.title for item in by_day[date(2026, 5, 5)]], ["Morning routine"]
        )
        self.assertEqual(self.db.topics_by_day(date(2026, 5, 12), date(2026, 5, 11)), {})

    def test_delete_topic_clears_progress(self) -> None:
        saved = self.db.add_topic(topic())
        assert saved.id is not None
        subtask_id = saved.subtasks[0].id
        assert subtask_id is not None
        self.db.set_subtask_progress(subtask_id, date(2026, 5, 4), 100)
        self.db.set_topic_progress(saved.id, date(2026, 5, 4), 42)
        self.assertTrue(self.db.delete_topic(saved.id))
        self.assertFalse(self.db.delete_topic(saved.id))
        self.assertIsNone(self.db.get_topic(saved.id))
        with self.assertRaises(DatabaseError):
            self.db.set_subtask_progress(subtask_id, date(2026, 5, 4), 0)
        with self.assertRaises(DatabaseError):
            self.db.set_topic_progress(saved.id, date(2026, 5, 4), 42)

    def test_invalid_subtask_and_status_rejected(self) -> None:
        saved = self.db.add_topic(topic())
        subtask_id = saved.subtasks[0].id
        assert subtask_id is not None
        with self.assertRaises(ValidationError):
            self.db.set_subtask_progress(subtask_id, date(2026, 5, 4), 60)
        with self.assertRaises(DatabaseError):
            self.db.update_topic(topic(id=999))

    def test_schema_migration_keeps_existing_events(self) -> None:
        self.db.close()
        connection = sqlite3.connect(str(self.path))
        connection.execute("DROP TABLE IF EXISTS task_topics")
        connection.execute("DROP TABLE IF EXISTS task_subtasks")
        connection.execute("DROP TABLE IF EXISTS task_progress")
        connection.execute("DROP TABLE IF EXISTS task_topic_progress")
        connection.execute("PRAGMA user_version = 1")
        connection.commit()
        connection.close()
        self.db = Database(self.path)
        tables = {
            row[0]
            for row in self.db._conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        self.assertTrue(
            {
                "events",
                "settings",
                "task_topics",
                "task_subtasks",
                "task_progress",
                "task_topic_progress",
            }
            <= tables
        )
        self.assertEqual(self.db._conn.execute("PRAGMA user_version").fetchone()[0], 3)


class TaskUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        cls.app = QApplication.instance() or QApplication([])

    def test_status_change_keeps_window_open(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            db = Database(Path(temp) / "tasks.db")
            db.add_topic(topic())
            window = MainWindow(db, ReminderEngine(db))
            window.show()
            closed: list[bool] = []
            original = window.closeEvent

            def spy(event: object) -> None:
                closed.append(True)
                original(event)  # type: ignore[arg-type]

            window.closeEvent = spy  # type: ignore[method-assign]
            row = window.findChild(SubtaskRow)
            assert row is not None
            row.status_buttons[100].click()
            self.app.processEvents()
            self.assertTrue(window.isVisible())
            self.assertFalse(closed)
            window._really_quit = True
            window.close()
            db.close()

    def test_subtask_status_buttons_update_and_emit(self) -> None:
        subtask = Subtask("Water")
        subtask.id = 3
        row = SubtaskRow(subtask, 25)
        received: list[tuple[int, int]] = []
        row.statusChanged.connect(lambda subtask_id, status: received.append((subtask_id, status)))

        row.status_buttons[75].click()

        self.assertEqual(received, [(3, 75)])
        self.assertEqual(row.percent.text(), "75%")
        self.assertTrue(row.status_buttons[75].isChecked())

    def test_status_buttons_have_visible_labelled_section(self) -> None:
        row = SubtaskRow(Subtask("Water"), 50)

        self.assertGreaterEqual(row.sizeHint().height(), 50)
        for value, button in row.status_buttons.items():
            self.assertEqual(button.text(), f"{value}%")
            self.assertGreaterEqual(button.width(), 34)
            self.assertGreaterEqual(button.height(), 22)

    def test_card_offers_explicit_percent_with_reset(self) -> None:
        day = date(2026, 5, 4)
        item = topic()
        item.id = 7
        card = TaskTopicCard(item, day)
        changed: list[tuple[int, int]] = []
        reset: list[int] = []
        card.percentChanged.connect(lambda topic_id, percent: changed.append((topic_id, percent)))
        card.percentReset.connect(lambda topic_id: reset.append(topic_id))

        card.percent_spin.setValue(42)
        self.assertEqual(changed, [(7, 42)])
        self.assertFalse(card.auto_button.isHidden())

        card.auto_button.click()
        self.assertEqual(reset, [7])
        self.assertEqual(card.percent_spin.value(), 0)


if __name__ == "__main__":
    unittest.main()
