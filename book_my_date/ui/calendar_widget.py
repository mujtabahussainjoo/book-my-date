"""Month calendar with multi-event day cells and distinct weekend styling."""

from __future__ import annotations

import calendar
from datetime import date

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ..core.calendar_utils import (
    month_grid,
    month_title,
    normalize_week_start,
    shift_month,
    weekday_headers,
    weekend_kind,
)
from ..core.models import CATEGORIES, Event
from . import icons
from .theme import (
    FAINT,
    MUTED,
    repolish,
)
from .widgets import EventChip, IconButton

MAX_VISIBLE_EVENTS = 3


class DayCell(QWidget):
    selected = Signal(object)
    eventActivated = Signal(object)
    addRequested = Signal(object)

    def __init__(
        self,
        day: date,
        *,
        accent: str = "indigo",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.day = day
        self._accent = accent
        self.setObjectName("DayCell")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(88)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._build()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(7, 6, 7, 6)
        layout.setSpacing(3)

        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        self.number = QLabel(str(self.day.day))
        self.number.setObjectName("DayNumber")
        self.number.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.number.setFixedSize(27, 22)
        top.addWidget(self.number, 0, Qt.AlignmentFlag.AlignLeft)
        top.addStretch(1)
        layout.addLayout(top)

        self.chips = QVBoxLayout()
        self.chips.setContentsMargins(0, 0, 0, 0)
        self.chips.setSpacing(2)
        layout.addLayout(self.chips)
        layout.addStretch(1)

    def refresh(
        self,
        events: list[Event],
        *,
        selected: bool,
        today: date,
        current_month: int,
    ) -> None:
        weekend = weekend_kind(self.day)
        outside = self.day.month != current_month
        is_today = self.day == today

        self.setProperty("weekend", weekend if weekend else None)
        self.setProperty("outside", "true" if outside else None)
        self.setProperty("selected", "true" if selected else None)
        self.setProperty("today", "true" if is_today else None)
        repolish(self)

        self.number.setText(str(self.day.day))
        self.number.setObjectName("TodayNumber" if is_today else "DayNumber")
        self.number.setAlignment(Qt.AlignmentFlag.AlignCenter)
        repolish(self.number)

        self.setToolTip(
            f"{self.day.strftime('%A, %d %B %Y')} · "
            f"{len(events)} event{'s' if len(events) != 1 else ''}"
        )

        while self.chips.count():
            item = self.chips.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        visible = events[:MAX_VISIBLE_EVENTS]
        for event in visible:
            chip = EventChip(
                event,
                self.day,
                continuation=event.start_at.date() != self.day,
            )
            chip.clicked.connect(self.eventActivated)
            self.chips.addWidget(chip)

        hidden = len(events) - len(visible)
        if hidden > 0:
            more = QLabel(f"+{hidden} more")
            more.setObjectName("MoreLabel")
            more.setStyleSheet(f"color: {MUTED}; font-size: 10px; font-weight: 600;")
            self.chips.addWidget(more)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self.selected.emit(self.day)
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self.addRequested.emit(self.day)
        super().mouseDoubleClickEvent(event)


class CalendarWidget(QWidget):
    monthChanged = Signal(int, int)
    dateSelected = Signal(object)
    eventActivated = Signal(object)
    addRequested = Signal(object)

    def __init__(
        self,
        *,
        week_start: int = 0,
        accent: str = "indigo",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("CalendarCard")
        self._week_start = normalize_week_start(week_start)
        self._accent = accent
        self._events_by_day: dict[date, list[Event]] = {}
        self._year = date.today().year
        self._month = date.today().month
        self._selected = date.today()
        self._today = date.today()
        self._cells: list[list[DayCell]] = []
        self._grid: QGridLayout | None = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(18, 16, 18, 14)
        outer.setSpacing(10)

        header = QHBoxLayout()
        header.setSpacing(10)
        titles = QVBoxLayout()
        titles.setSpacing(0)
        self.title_label = QLabel(month_title(self._year, self._month))
        self.title_label.setObjectName("PageTitle")
        titles.addWidget(self.title_label)
        self.summary_label = QLabel("")
        self.summary_label.setObjectName("Muted")
        self.summary_label.setStyleSheet(f"color: {MUTED}; font-size: 11px;")
        titles.addWidget(self.summary_label)
        header.addLayout(titles)
        header.addStretch(1)

        today_button = QPushButton("Today")
        today_button.setProperty("variant", "secondary")
        today_button.setCursor(Qt.CursorShape.PointingHandCursor)
        today_button.setFixedHeight(34)
        today_button.clicked.connect(self.go_today)
        header.addWidget(today_button)

        nav = QFrame()
        nav.setObjectName("SoftCard")
        nav_layout = QHBoxLayout(nav)
        nav_layout.setContentsMargins(3, 3, 3, 3)
        nav_layout.setSpacing(1)
        self.prev_button = IconButton("chevron-left", size=30, icon_size=16, tooltip="Previous month")
        self.next_button = IconButton("chevron-right", size=30, icon_size=16, tooltip="Next month")
        self.prev_button.clicked.connect(lambda: self._change_month(-1))
        self.next_button.clicked.connect(lambda: self._change_month(1))
        nav_layout.addWidget(self.prev_button)
        nav_layout.addWidget(self.next_button)
        header.addWidget(nav)
        outer.addLayout(header)

        self.grid_host = QWidget()
        self.grid_host.setStyleSheet("background: transparent;")
        outer.addWidget(self.grid_host, 1)

        legend = QHBoxLayout()
        legend.setSpacing(12)
        for key in ("work", "personal", "meeting", "birthday", "holiday", "other"):
            cat = CATEGORIES[key]
            label = QLabel(cat.label)
            label.setStyleSheet(f"color: {FAINT}; font-size: 9px; font-weight: 600;")
            dot = QLabel()
            dot.setPixmap(icons.dot(cat.color, 7).pixmap(7, 7))
            dot.setFixedSize(7, 7)
            legend.addWidget(dot)
            legend.addWidget(label)
        legend.addStretch(1)
        hint = QLabel("Double-click a day to add an event")
        hint.setStyleSheet(f"color: {FAINT}; font-size: 9px;")
        legend.addWidget(hint)
        outer.addLayout(legend)

        self._rebuild_grid()

    # ------------------------------------------------------------------ public
    @property
    def selected_date(self) -> date:
        return self._selected

    @property
    def year(self) -> int:
        return self._year

    @property
    def month(self) -> int:
        return self._month

    def set_week_start(self, week_start: int) -> None:
        normalized = normalize_week_start(week_start)
        if normalized == self._week_start:
            return
        self._week_start = normalized
        self._rebuild_grid()

    def set_accent(self, accent: str) -> None:
        self._accent = accent
        self._rebuild_grid()

    def set_events(self, events_by_day: dict[date, list[Event]]) -> None:
        self._events_by_day = events_by_day
        self._refresh_cells()
        self._update_summary()

    def set_month(
        self,
        year: int,
        month: int,
        *,
        select_day: date | None = None,
        emit: bool = True,
    ) -> None:
        self._year = year
        self._month = month
        last_day = calendar.monthrange(year, month)[1]
        if select_day is not None:
            self._selected = select_day
        elif (self._selected.year, self._selected.month) != (year, month):
            self._selected = date(year, month, min(self._selected.day, last_day))
        self.title_label.setText(month_title(year, month))
        self._rebuild_grid()
        self._update_summary()
        if emit:
            self.dateSelected.emit(self._selected)

    def show_date(self, day: date, *, emit: bool = True) -> None:
        self._today = date.today()
        if (day.year, day.month) != (self._year, self._month):
            self.set_month(day.year, day.month, select_day=day, emit=emit)
            self.monthChanged.emit(day.year, day.month)
        else:
            self.set_selected(day, emit=emit)

    def set_selected(self, day: date, *, emit: bool = True) -> None:
        if (day.year, day.month) != (self._year, self._month):
            self.show_date(day, emit=emit)
            return
        previous = self._selected
        self._selected = day
        self._today = date.today()
        if (previous.year, previous.month) == (day.year, day.month):
            self._refresh_cells()
        else:
            self._refresh_cells()
        if emit:
            self.dateSelected.emit(day)

    def go_today(self) -> None:
        self.show_date(date.today())

    def refresh_today(self) -> None:
        today = date.today()
        if today != self._today:
            self._today = today
            self._refresh_cells()

    # ----------------------------------------------------------------- internal
    def _change_month(self, delta: int) -> None:
        year, month = shift_month(self._year, self._month, delta)
        last_day = calendar.monthrange(year, month)[1]
        target = date(year, month, min(self._selected.day, last_day))
        self.set_month(year, month, select_day=target)
        self.monthChanged.emit(year, month)

    def _clear_layout(self) -> None:
        if self._grid is not None:
            while self._grid.count():
                item = self._grid.takeAt(0)
                widget = item.widget()
                if widget is not None:
                    widget.deleteLater()
        self._cells = []

    def _rebuild_grid(self) -> None:
        if self._grid is None:
            self._grid = QGridLayout(self.grid_host)
            self._grid.setContentsMargins(0, 0, 0, 0)
            self._grid.setHorizontalSpacing(6)
            self._grid.setVerticalSpacing(6)
        else:
            self._clear_layout()

        for index, label_text in enumerate(weekday_headers(self._week_start)):
            actual = (self._week_start + index) % 7
            kind = "sat" if actual == 5 else "sun" if actual == 6 else None
            label = QLabel(label_text.upper())
            label.setObjectName("WeekendHeader")
            label.setProperty("weekend", kind)
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setFixedHeight(26)
            font = QFont(label.font())
            font.setPointSizeF(8.5)
            label.setFont(font)
            self._grid.addWidget(label, 0, index)

        self._cells = []
        for row, week in enumerate(month_grid(self._year, self._month, self._week_start), start=1):
            row_cells: list[DayCell] = []
            for column, day in enumerate(week):
                cell = DayCell(day, accent=self._accent)
                cell.selected.connect(self._on_cell_selected)
                cell.eventActivated.connect(self.eventActivated)
                cell.addRequested.connect(self.addRequested)
                self._grid.addWidget(cell, row, column)
                row_cells.append(cell)
            self._cells.append(row_cells)
            self._grid.setRowStretch(row, 1)

        for column in range(7):
            self._grid.setColumnStretch(column, 1)

        self._refresh_cells()

    def _refresh_cells(self) -> None:
        for row in self._cells:
            for cell in row:
                events = self._events_by_day.get(cell.day, [])
                cell.refresh(
                    events,
                    selected=cell.day == self._selected,
                    today=self._today,
                    current_month=self._month,
                )

    def _update_summary(self) -> None:
        unique: set[int] = set()
        for day, events in self._events_by_day.items():
            if day.year == self._year and day.month == self._month:
                unique.update(event.id for event in events if event.id is not None)
        count = len(unique)
        self.summary_label.setText(
            "No events this month"
            if count == 0
            else f"{count} event{'s' if count != 1 else ''} this month"
        )

    def _on_cell_selected(self, day: date) -> None:
        self.set_selected(day)
