"""Pure date helpers used by the calendar UI and tests."""

from __future__ import annotations

import calendar
from datetime import date, timedelta
from typing import Iterable, Sequence

from .models import Event

WEEKDAY_SHORT: tuple[str, ...] = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
WEEKDAY_LONG: tuple[str, ...] = (
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
)
MONTH_NAMES: tuple[str, ...] = (
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)


def normalize_week_start(week_start: int) -> int:
    """Return the weekday index (Monday=0, Sunday=6) for the first column."""

    return 0 if int(week_start) % 7 == 0 else 6


def weekday_headers(week_start: int = 0) -> list[str]:
    start = normalize_week_start(week_start)
    return [WEEKDAY_SHORT[(start + index) % 7] for index in range(7)]


def weekend_positions(week_start: int = 0) -> set[int]:
    start = normalize_week_start(week_start)
    return {index for index in range(7) if (start + index) % 7 in (5, 6)}


def weekend_kind(day: date) -> str:
    return "sat" if day.weekday() == 5 else "sun" if day.weekday() == 6 else ""


def month_grid(year: int, month: int, week_start: int = 0) -> list[list[date]]:
    """Build a stable six-week grid that includes neighbouring month days."""

    if not 1 <= month <= 12:
        raise ValueError("month must be between 1 and 12")
    start = normalize_week_start(week_start)
    first = date(year, month, 1)
    offset = (first.weekday() - start) % 7
    grid_start = first - timedelta(days=offset)
    return [
        [grid_start + timedelta(days=week * 7 + day) for day in range(7)]
        for week in range(6)
    ]


def month_bounds(year: int, month: int) -> tuple[date, date]:
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, 1), date(year, month, last_day)


def shift_month(year: int, month: int, delta: int) -> tuple[int, int]:
    index = (year * 12 + month - 1) + delta
    return index // 12, index % 12 + 1


def month_title(year: int, month: int) -> str:
    return f"{MONTH_NAMES[month - 1]} {year}"


def weekday_name(day: date) -> str:
    return WEEKDAY_LONG[day.weekday()]


def short_date(day: date) -> str:
    return f"{WEEKDAY_SHORT[day.weekday()]}, {day.day} {MONTH_NAMES[day.month - 1][:3]}"


def long_date(day: date) -> str:
    return f"{weekday_name(day)}, {day.day} {MONTH_NAMES[day.month - 1]} {day.year}"


def relative_day_label(day: date, today: date | None = None) -> str:
    today = today or date.today()
    difference = (day - today).days
    if difference == 0:
        return "Today"
    if difference == 1:
        return "Tomorrow"
    if difference == -1:
        return "Yesterday"
    if 1 < difference < 7:
        return f"In {difference} days"
    if -7 < difference < -1:
        return f"{abs(difference)} days ago"
    return short_date(day)


def events_on_day(events: Iterable[Event], day: date) -> list[Event]:
    matches = [event for event in events if event.occurs_on(day)]
    return sorted(matches, key=lambda event: (not event.all_day, event.start_at, event.id or 0))


def group_events_by_day(events: Iterable[Event]) -> dict[date, list[Event]]:
    grouped: dict[date, list[Event]] = {}
    for event in events:
        current = event.start_at.date()
        last = event.end_at.date()
        while current <= last:
            grouped.setdefault(current, []).append(event)
            current += timedelta(days=1)
    for day_events in grouped.values():
        day_events.sort(key=lambda event: (not event.all_day, event.start_at, event.id or 0))
    return grouped


def visible_events(events: Sequence[Event], limit: int = 3) -> tuple[list[Event], int]:
    """Return the events that fit in a day cell plus the hidden remainder."""

    if limit < 0:
        raise ValueError("limit must not be negative")
    return list(events[:limit]), max(0, len(events) - limit)


def count_events(events: Iterable[Event]) -> int:
    return sum(1 for _ in events)
