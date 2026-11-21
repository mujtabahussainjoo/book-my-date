"""Domain models and validation for Book My Date."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import date, datetime, time, timedelta
from typing import Final

MAX_TITLE_LENGTH: Final = 120
MAX_DESCRIPTION_LENGTH: Final = 5000
MAX_LOCATION_LENGTH: Final = 160
MAX_REMINDER_MINUTES: Final = 7 * 24 * 60
MAX_TOPIC_TITLE_LENGTH: Final = 120
MAX_SUBTASK_TITLE_LENGTH: Final = 120
MAX_SUBTASKS_PER_TOPIC: Final = 24

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


def _as_date(value: date | str) -> date:
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


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


# ----------------------------------------------------------- repeating tasks

PROGRESS_STATUSES: Final[tuple[int, ...]] = (0, 25, 50, 75, 100)
STATUS_LABELS: Final[dict[int, str]] = {
    0: "Not started",
    25: "Just begun",
    50: "Halfway there",
    75: "Almost done",
    100: "Complete",
}
STATUS_COLORS: Final[dict[int, str]] = {
    0: "#94A3B8",
    25: "#0EA5E9",
    50: "#F59E0B",
    75: "#8B5CF6",
    100: "#0E9F6E",
}
STATUS_SOFT_COLORS: Final[dict[int, str]] = {
    0: "#F1F5F9",
    25: "#E0F2FE",
    50: "#FEF3C7",
    75: "#EDE9FE",
    100: "#E7F8F1",
}
DEFAULT_SUBTASK_COLOR: Final = "indigo"
WEEKDAY_INITIALS: Final[tuple[str, ...]] = ("M", "T", "W", "T", "F", "S", "S")
WEEKDAY_LABELS: Final[tuple[str, ...]] = (
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
)


@dataclass(frozen=True)
class SubtaskColor:
    key: str
    label: str
    color: str
    soft_color: str


SUBTASK_COLORS: dict[str, SubtaskColor] = {
    "indigo": SubtaskColor("indigo", "Indigo", "#5B5BD6", "#EEEFFE"),
    "emerald": SubtaskColor("emerald", "Emerald", "#0E9F6E", "#E7F8F1"),
    "ocean": SubtaskColor("ocean", "Ocean", "#0E7490", "#E0F4F8"),
    "amber": SubtaskColor("amber", "Amber", "#D97706", "#FEF3E2"),
    "violet": SubtaskColor("violet", "Violet", "#7C3AED", "#F1E9FE"),
    "rose": SubtaskColor("rose", "Rose", "#E11D74", "#FDEBF3"),
}
DEFAULT_WEEKDAYS: Final = frozenset(range(7))


def validate_status(status: int) -> int:
    value = int(status)
    if value not in PROGRESS_STATUSES:
        raise ValidationError(
            "Progress must be one of " + ", ".join(str(item) for item in PROGRESS_STATUSES) + "."
        )
    return value


def validate_percent(percent: int) -> int:
    value = int(percent)
    if not 0 <= value <= 100:
        raise ValidationError("Overall completion must be between 0% and 100%.")
    return value


def status_color(status: int) -> str:
    value = validate_status(status)
    return STATUS_COLORS[value]


def nearest_status(percent: int) -> int:
    """Snap an averaged completion percentage to the closest progress step."""

    return min(PROGRESS_STATUSES, key=lambda level: abs(level - int(percent)))


def completion_color(percent: int) -> str:
    return STATUS_COLORS[nearest_status(percent)]


def completion_soft_color(percent: int) -> str:
    return STATUS_SOFT_COLORS[nearest_status(percent)]


def subtask_color(key: str) -> SubtaskColor:
    return SUBTASK_COLORS.get(key, SUBTASK_COLORS[DEFAULT_SUBTASK_COLOR])


@dataclass
class Subtask:
    title: str
    color: str = DEFAULT_SUBTASK_COLOR
    id: int | None = None
    position: int = 0

    def __post_init__(self) -> None:
        self.title = (self.title or "").strip()
        self.color = (self.color or DEFAULT_SUBTASK_COLOR).strip().lower()
        if not self.title:
            raise ValidationError("Please enter a title for each subtask.")
        if len(self.title) > MAX_SUBTASK_TITLE_LENGTH:
            raise ValidationError(
                f"Subtasks can be at most {MAX_SUBTASK_TITLE_LENGTH} characters."
            )
        if self.color not in SUBTASK_COLORS:
            raise ValidationError(f"Unknown subtask color: {self.color!r}.")

    @property
    def meta(self) -> SubtaskColor:
        return subtask_color(self.color)

    def copy(self, **changes: object) -> Subtask:
        return replace(self, **changes)


@dataclass
class TaskTopic:
    """A repeatable topic made of subtasks whose progress is stored per date."""

    title: str
    subtasks: list[Subtask] = field(default_factory=list)
    id: int | None = None
    apply_to_all_dates: bool = True
    start_date: date = field(default_factory=date.today)
    end_date: date | None = None
    weekdays: frozenset[int] = field(default_factory=lambda: DEFAULT_WEEKDAYS)
    progress: dict[int, int] = field(default_factory=dict)
    manual_progress: dict[date, int] = field(default_factory=dict)
    created_at: datetime | None = field(default=None)
    updated_at: datetime | None = field(default=None)

    def __post_init__(self) -> None:
        self.title = (self.title or "").strip()
        if not self.title:
            raise ValidationError("Please enter a title for the task topic.")
        if len(self.title) > MAX_TOPIC_TITLE_LENGTH:
            raise ValidationError(
                f"Task topics can be at most {MAX_TOPIC_TITLE_LENGTH} characters."
            )
        self.subtasks = list(self.subtasks)
        if len(self.subtasks) > MAX_SUBTASKS_PER_TOPIC:
            raise ValidationError(
                f"A task topic can have at most {MAX_SUBTASKS_PER_TOPIC} subtasks."
            )
        self.apply_to_all_dates = bool(self.apply_to_all_dates)
        self.weekdays = frozenset(int(day) for day in self.weekdays)
        if any(day < 0 or day > 6 for day in self.weekdays):
            raise ValidationError("Weekdays must be between Monday and Sunday.")
        if not self.apply_to_all_dates and not self.weekdays:
            raise ValidationError("Select at least one weekday for this task topic.")
        if self.end_date is not None and self.end_date < self.start_date:
            raise ValidationError("The end date cannot be before the start date.")
        self.progress = {
            int(subtask_id): validate_status(status)
            for subtask_id, status in self.progress.items()
        }
        self.manual_progress = {
            _as_date(day): validate_percent(percent)
            for day, percent in self.manual_progress.items()
        }
        if self.created_at is not None:
            self.created_at = as_local(self.created_at)
        if self.updated_at is not None:
            self.updated_at = as_local(self.updated_at)

    def applies_on(self, day: date) -> bool:
        if self.apply_to_all_dates:
            return True
        if day < self.start_date:
            return False
        if self.end_date is not None and day > self.end_date:
            return False
        return day.weekday() in self.weekdays

    def status_for(self, subtask_id: int | None) -> int:
        if subtask_id is None:
            return 0
        return self.progress.get(subtask_id, 0)

    def completion(self) -> int:
        if not self.subtasks:
            return 0
        total = sum(self.status_for(subtask.id) for subtask in self.subtasks)
        return int(total / len(self.subtasks) + 0.5)

    def completion_for(self, day: date | None = None) -> int:
        if day is not None and day in self.manual_progress:
            return self.manual_progress[day]
        return self.completion()

    def has_manual_progress(self, day: date) -> bool:
        return day in self.manual_progress

    def completed_count(self) -> int:
        return sum(
            1 for subtask in self.subtasks if self.status_for(subtask.id) == 100
        )

    def weekday_list(self) -> list[int]:
        return sorted(self.weekdays)

    def schedule_label(self) -> str:
        if self.apply_to_all_dates:
            return "Every date"
        span = f"from {self.start_date.strftime('%d %b %Y')}"
        if self.end_date is not None:
            span += f" to {self.end_date.strftime('%d %b %Y')}"
        names = ", ".join(WEEKDAY_LABELS[day][:3] for day in self.weekday_list())
        return f"{names} · {span}"

    def copy(self, **changes: object) -> TaskTopic:
        result = replace(self, **changes)
        result.subtasks = [subtask.copy() for subtask in result.subtasks]
        result.progress = dict(result.progress)
        result.manual_progress = dict(result.manual_progress)
        result.weekdays = frozenset(result.weekdays)
        return result
