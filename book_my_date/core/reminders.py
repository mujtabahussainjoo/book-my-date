"""Reminder polling logic, kept independent from the GUI toolkit."""

from __future__ import annotations

from datetime import datetime
from typing import Callable

from .database import Database
from .models import Event, local_now


class ReminderEngine:
    """Finds due reminders exactly once and supports snoozing them."""

    def __init__(
        self,
        database: Database,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.database = database
        self.clock = clock or local_now

    def pop_due(self, now: datetime | None = None) -> list[Event]:
        moment = now or self.clock()
        events = self.database.due_reminders(moment)
        if events:
            self.database.mark_notified(
                event.id for event in events if event.id is not None
            )
        return events

    def snooze(self, event: Event, minutes: int = 10) -> datetime | None:
        if event.id is None:
            return None
        return self.database.snooze_reminder(
            event.id, minutes=minutes, now=self.clock()
        )
