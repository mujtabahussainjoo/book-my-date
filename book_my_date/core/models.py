"""Domain models and validation for Book My Date."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import date, datetime, time, timedelta
from typing import Final

MAX_TITLE_LENGTH: Final = 120
MAX_DESCRIPTION_LENGTH: Final = 5000
MAX_LOCATION_LENGTH: Final = 160
MAX_REMINDER_MINUTES: Final = 7 * 24 * 60

CATEGORY_KEYS: Final = ("work", "personal", "meeting", "birthday", "holiday", "other")


class ValidationError(ValueError):
    """Raised when an event or setting fails validation."""


@dataclass(frozen=True)
class Category:
    key: str
    label: str
    color: str
    soft_color: str
    text_color: str


CATEGORIES: dict[str, Category] = {
    "work": Category("work", "Work", "#5B5BD6", "#EEEFFE", "#3F3F97"),
    "personal": Category("personal", "Personal", "#0E9F6E", "#E7F8F1", "#0B6B4B"),
    "meeting": Category("meeting", "Meeting", "#0B84D8", "#E8F3FD", "#0B5C97"),
    "birthday": Category("birthday", "Birthday", "#E11D74", "#FDEBF3", "#A30F51"),
    "holiday": Category("holiday", "Holiday", "#D97706", "#FEF3E2", "#92500A"),
    "other": Category("other", "Other", "#64748B", "#F1F5F9", "#475569"),
}

DEFAULT_CATEGORY: Final = "personal"
DEFAULT_REMINDER_MINUTES: Final = 15

REMINDER_CHOICES: Final[tuple[tuple[int | None, str], ...]] = (
    (None, "No reminder"),
    (0, "At start time"),
    (5, "5 minutes before"),
    (10, "10 minutes before"),
    (15, "15 minutes before"),
    (30, "30 minutes before"),
    (60, "1 hour before"),
    (120, "2 hours before"),
    (1440, "1 day before"),
    (10080, "1 week before"),
)


def local_now() -> datetime:
    return datetime.now().astimezone()


def as_local(value: datetime) -> datetime:
    """Attach the local timezone to naive values and convert aware values."""

    if value.tzinfo is None:
        return value.astimezone()
    return value.astimezone()


def reminder_label(minutes: int | None) -> str:
    if minutes is None:
        return "No reminder"
    for value, label in REMINDER_CHOICES:
        if value == minutes:
            return label
    if minutes % 1440 == 0:
        days = minutes // 1440
        return f"{days} day{'s' if days != 1 else ''} before"
    if minutes % 60 == 0:
        hours = minutes // 60
        return f"{hours} hour{'s' if hours != 1 else ''} before"
    return f"{minutes} minutes before"


def category_for(key: str) -> Category:
    return CATEGORIES.get(key, CATEGORIES[DEFAULT_CATEGORY])


@dataclass
class Event:
    title: str
    start_at: datetime
    end_at: datetime
    id: int | None = None
    description: str = ""
    location: str = ""
    all_day: bool = False
    category: str = DEFAULT_CATEGORY
    reminder_minutes: int | None = DEFAULT_REMINDER_MINUTES
    notified: bool = False
    created_at: datetime | None = field(default=None)
    updated_at: datetime | None = field(default=None)

    def __post_init__(self) -> None:
        self.title = (self.title or "").strip()
        self.description = (self.description or "").strip()
        self.location = (self.location or "").strip()
        self.category = (self.category or DEFAULT_CATEGORY).strip().lower()

        if not self.title:
            raise ValidationError("Please enter a title for the event.")
        if len(self.title) > MAX_TITLE_LENGTH:
            raise ValidationError(f"Titles can be at most {MAX_TITLE_LENGTH} characters.")
        if len(self.description) > MAX_DESCRIPTION_LENGTH:
            raise ValidationError(
                f"Descriptions can be at most {MAX_DESCRIPTION_LENGTH} characters."
            )
        if len(self.location) > MAX_LOCATION_LENGTH:
            raise ValidationError(
                f"Locations can be at most {MAX_LOCATION_LENGTH} characters."
            )
        if self.category not in CATEGORIES:
            raise ValidationError(f"Unknown event category: {self.category!r}.")

        self.start_at = as_local(self.start_at)
        self.end_at = as_local(self.end_at)

        if self.reminder_minutes is not None:
            if not isinstance(self.reminder_minutes, int):
                raise ValidationError("Reminder must be a whole number of minutes.")
            if self.reminder_minutes < 0 or self.reminder_minutes > MAX_REMINDER_MINUTES:
                raise ValidationError(
                    "Reminder must be between 0 minutes and one week."
                )

        if self.all_day:
            self.start_at = datetime.combine(self.start_at.date(), time.min).astimezone()
            self.end_at = datetime.combine(self.end_at.date(), time(23, 59, 59)).astimezone()
        elif self.end_at <= self.start_at:
            raise ValidationError("The end time must be after the start time.")

        if self.end_at < self.start_at:
            raise ValidationError("The end date cannot be before the start date.")

        if self.created_at is not None:
            self.created_at = as_local(self.created_at)
        if self.updated_at is not None:
            self.updated_at = as_local(self.updated_at)

        if self.all_day:
            self.notified = bool(self.notified)

    @property
    def category_meta(self) -> Category:
        return category_for(self.category)

    @property
    def reminder_at(self) -> datetime | None:
        """The moment a reminder should be shown, in local time."""

        if self.reminder_minutes is None:
            return None
        base = self.start_at
        if self.all_day:
            base = datetime.combine(self.start_at.date(), time(9, 0)).astimezone()
        return base - timedelta(minutes=self.reminder_minutes)

    @property
    def duration_minutes(self) -> int:
        if self.all_day:
            return (self.end_at.date() - self.start_at.date()).days + 1
        return max(1, int((self.end_at - self.start_at).total_seconds() // 60))

    def occurs_on(self, day: date) -> bool:
        return self.start_at.date() <= day <= self.end_at.date()

    def is_past(self, now: datetime | None = None) -> bool:
        return self.end_at < (as_local(now) if now else local_now())

    def display_time_range(self) -> str:
        if self.all_day:
            nights = (self.end_at.date() - self.start_at.date()).days
            if nights <= 0:
                return "All day"
            return f"All day · {nights + 1} days"
        start = self.start_at.strftime("%H:%M")
        if self.start_at.date() == self.end_at.date():
            return f"{start} – {self.end_at.strftime('%H:%M')}"
        return f"{start} – {self.end_at.strftime('%a %d %b, %H:%M')}"

    def short_description(self, limit: int = 140) -> str:
        text = " ".join(self.description.split())
        if len(text) <= limit:
            return text
        return text[: limit - 1].rstrip() + "…"

    def notification_body(self) -> str:
        parts = [self.display_time_range()]
        if self.location:
            parts.append(self.location)
        return " · ".join(parts)

    def copy(self, **changes: object) -> Event:
        return replace(self, **changes)
