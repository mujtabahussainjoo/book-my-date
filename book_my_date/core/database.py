"""SQLite persistence layer with a small, explicit schema."""

from __future__ import annotations

import logging
import sqlite3
import threading
from contextlib import suppress
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

from .models import (
    DEFAULT_CATEGORY,
    DEFAULT_REMINDER_MINUTES,
    Event,
    as_local,
    local_now,
)

LOGGER = logging.getLogger(__name__)
SCHEMA_VERSION = 1

DEFAULT_SETTINGS: dict[str, str] = {
    "week_start": "0",
    "accent": "indigo",
    "notifications": "true",
    "sound": "true",
    "close_to_tray": "true",
    "default_reminder": str(DEFAULT_REMINDER_MINUTES),
    "window_geometry": "",
}


class DatabaseError(RuntimeError):
    pass


def _to_utc_text(value: datetime) -> str:
    return as_local(value).astimezone(timezone.utc).isoformat(timespec="seconds")


def _from_text(value: str | None) -> datetime | None:
    if not value:
        return None
    return as_local(datetime.fromisoformat(value))


def _day_start(day: date) -> str:
    return _to_utc_text(datetime.combine(day, time.min))


class Database:
    """Thread-safe wrapper around a single SQLite connection."""

    def __init__(self, path: str | Path) -> None:
        self.path = str(path)
        if self.path != ":memory:":
            Path(self.path).expanduser().parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._closed = False
        self._conn = sqlite3.connect(
            self.path,
            timeout=10.0,
            check_same_thread=False,
        )
        self._conn.row_factory = sqlite3.Row
        with self._lock:
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA synchronous=NORMAL")
            self._conn.execute("PRAGMA busy_timeout=10000")
            self._migrate()

    # ------------------------------------------------------------------ schema
    def _migrate(self) -> None:
        version = int(self._conn.execute("PRAGMA user_version").fetchone()[0])
        if version > SCHEMA_VERSION:
            raise DatabaseError(
                "This database was created by a newer version of Book My Date."
            )
        if version == 0:
            self._conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    description TEXT NOT NULL DEFAULT '',
                    location TEXT NOT NULL DEFAULT '',
                    start_at TEXT NOT NULL,
                    end_at TEXT NOT NULL,
                    all_day INTEGER NOT NULL DEFAULT 0,
                    category TEXT NOT NULL DEFAULT 'personal',
                    reminder_minutes INTEGER,
                    reminder_at TEXT,
                    notified INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_events_start_at
                    ON events(start_at);
                CREATE INDEX IF NOT EXISTS idx_events_end_at
                    ON events(end_at);
                CREATE INDEX IF NOT EXISTS idx_events_reminders
                    ON events(notified, reminder_at);

                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );

                PRAGMA user_version = 1;
                """
            )
            for key, value in DEFAULT_SETTINGS.items():
                self._conn.execute(
                    "INSERT OR IGNORE INTO settings(key, value) VALUES (?, ?)",
                    (key, value),
                )
            self._conn.commit()

    # ------------------------------------------------------------------ events
    def add_event(self, event: Event) -> Event:
        now = local_now()
        record = event.copy(id=None, notified=False, created_at=now, updated_at=now)
        values = self._event_values(record)
        with self._lock:
            cursor = self._conn.execute(
                """
                INSERT INTO events(
                    title, description, location, start_at, end_at, all_day,
                    category, reminder_minutes, reminder_at, notified,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                values,
            )
            self._conn.commit()
            event_id = int(cursor.lastrowid)
        return record.copy(id=event_id)

    def update_event(self, event: Event) -> Event:
        if event.id is None:
            raise DatabaseError("Cannot update an event without an id.")
        existing = self.get_event(event.id)
        if existing is None:
            raise DatabaseError("That event no longer exists.")

        schedule_changed = (
            existing.start_at != event.start_at
            or existing.reminder_minutes != event.reminder_minutes
            or existing.all_day != event.all_day
        )
        now = local_now()
        record = event.copy(
            notified=False if schedule_changed else event.notified,
            created_at=existing.created_at,
            updated_at=now,
        )
        values = self._event_values(record) + (record.id,)
        with self._lock:
            self._conn.execute(
                """
                UPDATE events SET
                    title = ?, description = ?, location = ?, start_at = ?,
                    end_at = ?, all_day = ?, category = ?, reminder_minutes = ?,
                    reminder_at = ?, notified = ?, created_at = ?, updated_at = ?
                WHERE id = ?
                """,
                values,
            )
            self._conn.commit()
        return record

    def delete_event(self, event_id: int) -> bool:
        with self._lock:
            cursor = self._conn.execute("DELETE FROM events WHERE id = ?", (event_id,))
            self._conn.commit()
            return cursor.rowcount > 0

    def get_event(self, event_id: int) -> Event | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM events WHERE id = ?", (event_id,)
            ).fetchone()
        return self._row_to_event(row) if row else None

    def list_events(
        self,
        start: date | None = None,
        end: date | None = None,
    ) -> list[Event]:
        clauses: list[str] = []
        params: list[Any] = []
        if start is not None:
            clauses.append("end_at >= ?")
            params.append(_day_start(start))
        if end is not None:
            clauses.append("start_at < ?")
            params.append(_day_start(end + timedelta(days=1)))
        sql = "SELECT * FROM events"
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY all_day DESC, start_at ASC, id ASC"
        with self._lock:
            rows = self._conn.execute(sql, params).fetchall()
        return [self._row_to_event(row) for row in rows]

    def events_for_day(self, day: date) -> list[Event]:
        return self.list_events(day, day)

    def events_for_month(self, year: int, month: int) -> list[Event]:
        first = date(year, month, 1)
        if month == 12:
            last = date(year, 12, 31)
        else:
            last = date(year, month + 1, 1) - timedelta(days=1)
        return self.list_events(first, last)

    def upcoming_events(
        self, limit: int = 5, now: datetime | None = None
    ) -> list[Event]:
        if limit <= 0:
            return []
        moment = _to_utc_text(now or local_now())
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT * FROM events
                WHERE end_at >= ?
                ORDER BY start_at ASC, id ASC
                LIMIT ?
                """,
                (moment, limit),
            ).fetchall()
        return [self._row_to_event(row) for row in rows]

    def search_events(self, query: str, limit: int = 50) -> list[Event]:
        term = query.strip()
        if not term or limit <= 0:
            return []
        escaped = (
            term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        )
        pattern = f"%{escaped}%"
        moment = _to_utc_text(local_now())
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT * FROM events
                WHERE (title LIKE ? ESCAPE '\\'
                    OR description LIKE ? ESCAPE '\\'
                    OR location LIKE ? ESCAPE '\\')
                ORDER BY
                    CASE WHEN end_at >= ? THEN 0 ELSE 1 END,
                    CASE WHEN end_at >= ? THEN start_at END ASC,
                    start_at DESC
                LIMIT ?
                """,
                (pattern, pattern, pattern, moment, moment, limit),
            ).fetchall()
        return [self._row_to_event(row) for row in rows]

    # --------------------------------------------------------------- reminders
    def due_reminders(self, now: datetime | None = None) -> list[Event]:
        moment = now or local_now()
        moment_text = _to_utc_text(moment)
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT * FROM events
                WHERE reminder_at IS NOT NULL
                  AND notified = 0
                  AND reminder_at <= ?
                  AND end_at >= ?
                ORDER BY reminder_at ASC, id ASC
                """,
                (moment_text, moment_text),
            ).fetchall()
        return [self._row_to_event(row) for row in rows]

    def mark_notified(self, event_ids: Iterable[int]) -> None:
        ids = [(int(event_id),) for event_id in event_ids]
        if not ids:
            return
        with self._lock:
            self._conn.executemany(
                "UPDATE events SET notified = 1 WHERE id = ?", ids
            )
            self._conn.commit()

    def snooze_reminder(
        self, event_id: int, minutes: int = 10, now: datetime | None = None
    ) -> datetime | None:
        if minutes <= 0:
            raise ValueError("Snooze minutes must be positive.")
        target = (now or local_now()) + timedelta(minutes=minutes)
        with self._lock:
            self._conn.execute(
                """
                UPDATE events
                SET reminder_at = ?, notified = 0, updated_at = ?
                WHERE id = ? AND reminder_minutes IS NOT NULL
                """,
                (_to_utc_text(target), _to_utc_text(local_now()), event_id),
            )
            self._conn.commit()
        return target

    def statistics(self, now: datetime | None = None) -> dict[str, int]:
        moment = now or local_now()
        moment_text = _to_utc_text(moment)
        today = moment.date()
        month_first = date(today.year, today.month, 1)
        week_end = today + timedelta(days=7)
        month_end = (month_first + timedelta(days=32)).replace(day=1) - timedelta(days=1)
        with self._lock:
            total = int(
                self._conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
            )
            today_count = int(
                self._conn.execute(
                    "SELECT COUNT(*) FROM events WHERE end_at >= ? AND start_at < ?",
                    (_day_start(today), _day_start(today + timedelta(days=1))),
                ).fetchone()[0]
            )
            upcoming = int(
                self._conn.execute(
                    "SELECT COUNT(*) FROM events WHERE end_at >= ? AND start_at < ?",
                    (moment_text, _day_start(week_end)),
                ).fetchone()[0]
            )
            reminders = int(
                self._conn.execute(
                    """
                    SELECT COUNT(*) FROM events
                    WHERE reminder_minutes IS NOT NULL AND end_at >= ?
                    """,
                    (moment_text,),
                ).fetchone()[0]
            )
            this_month = int(
                self._conn.execute(
                    "SELECT COUNT(*) FROM events WHERE end_at >= ? AND start_at < ?",
                    (_day_start(month_first), _day_start(month_end + timedelta(days=1))),
                ).fetchone()[0]
            )
        return {
            "total": total,
            "today": today_count,
            "upcoming": upcoming,
            "reminders": reminders,
            "this_month": this_month,
        }

    # ---------------------------------------------------------------- settings
    def get_setting(self, key: str, default: str | None = None) -> str | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT value FROM settings WHERE key = ?", (key,)
            ).fetchone()
        if row is not None:
            return str(row["value"])
        if default is not None:
            return default
        return DEFAULT_SETTINGS.get(key)

    def set_setting(self, key: str, value: object) -> None:
        if isinstance(value, bool):
            text = "true" if value else "false"
        elif value is None:
            text = ""
        else:
            text = str(value)
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO settings(key, value) VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """,
                (key, text),
            )
            self._conn.commit()

    def get_bool(self, key: str, default: bool = False) -> bool:
        value = self.get_setting(key)
        if value is None:
            return default
        return value.strip().lower() in {"1", "true", "yes", "on"}

    def get_int(self, key: str, default: int = 0) -> int:
        value = self.get_setting(key)
        try:
            return int(value) if value is not None else default
        except (TypeError, ValueError):
            return default

    def all_settings(self) -> dict[str, str]:
        settings = dict(DEFAULT_SETTINGS)
        with self._lock:
            rows = self._conn.execute("SELECT key, value FROM settings").fetchall()
        settings.update({str(row["key"]): str(row["value"]) for row in rows})
        return settings

    # ------------------------------------------------------------------ backup
    def backup(self, destination: str | Path) -> Path:
        target = Path(destination).expanduser()
        target.parent.mkdir(parents=True, exist_ok=True)
        with self._lock:
            with suppress(sqlite3.Error):
                self._conn.execute("PRAGMA wal_checkpoint(FULL)")
            backup_conn = sqlite3.connect(str(target))
            try:
                self._conn.backup(backup_conn)
            finally:
                backup_conn.close()
        return target

    def checkpoint(self) -> None:
        with self._lock:
            with suppress(sqlite3.Error):
                self._conn.execute("PRAGMA wal_checkpoint(FULL)")

    def close(self) -> None:
        with self._lock:
            if self._closed:
                return
            self._closed = True
            with suppress(sqlite3.Error):
                self._conn.commit()
            self._conn.close()
            LOGGER.debug("Database closed: %s", self.path)

    def __enter__(self) -> Database:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    # ------------------------------------------------------------------ helpers
    @staticmethod
    def _event_values(event: Event) -> tuple[Any, ...]:
        reminder_at = event.reminder_at
        return (
            event.title,
            event.description,
            event.location,
            _to_utc_text(event.start_at),
            _to_utc_text(event.end_at),
            int(event.all_day),
            event.category or DEFAULT_CATEGORY,
            event.reminder_minutes,
            _to_utc_text(reminder_at) if reminder_at else None,
            int(event.notified),
            _to_utc_text(event.created_at or local_now()),
            _to_utc_text(event.updated_at or local_now()),
        )

    @staticmethod
    def _row_to_event(row: sqlite3.Row) -> Event:
        return Event(
            id=int(row["id"]),
            title=str(row["title"]),
            description=str(row["description"]),
            location=str(row["location"]),
            start_at=_from_text(str(row["start_at"])) or local_now(),
            end_at=_from_text(str(row["end_at"])) or local_now(),
            all_day=bool(row["all_day"]),
            category=str(row["category"]),
            reminder_minutes=(
                int(row["reminder_minutes"])
                if row["reminder_minutes"] is not None
                else None
            ),
            notified=bool(row["notified"]),
            created_at=_from_text(str(row["created_at"])),
            updated_at=_from_text(str(row["updated_at"])),
        )
