"""Selected-day agenda panel."""

from __future__ import annotations

from datetime import date

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ..core.calendar_utils import MONTH_NAMES, weekday_name
from ..core.models import Event, TaskTopic
from . import icons
from .task_widgets import TaskTopicCard
from .theme import FAINT, INK, MUTED, accent_for
from .widgets import EmptyState, EventCard, SectionLabel, make_divider


class DayPanel(QFrame):
    addRequested = Signal(object)
    taskRequested = Signal(object)
    editRequested = Signal(object)
    taskEditRequested = Signal(object)
    deleteRequested = Signal(object)
    progressChanged = Signal(int, int, int)
    percentChanged = Signal(int, int)
    percentReset = Signal(int)

    def __init__(
        self,
        *,
        accent: str = "indigo",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("Card")
        self._day = date.today()
        self._accent = accent
        self.setMinimumWidth(330)
        self.setMaximumWidth(390)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 16, 16, 12)
        outer.setSpacing(10)

        header = QHBoxLayout()
        header.setSpacing(8)
        titles = QVBoxLayout()
        titles.setSpacing(1)
        self.kicker = QLabel("TODAY")
        self.kicker.setStyleSheet(
            f"color: {accent_for(accent).color}; font-size: 9px; font-weight: 800;"
        )
        titles.addWidget(self.kicker)
        self.title = QLabel("")
        self.title.setStyleSheet(f"color: {INK}; font-size: 21px; font-weight: 700;")
        titles.addWidget(self.title)
        self.subtitle = QLabel("")
        self.subtitle.setStyleSheet(f"color: {MUTED}; font-size: 11px;")
        titles.addWidget(self.subtitle)
        header.addLayout(titles, 1)

        self.add_button = QPushButton("Add")
        self.add_button.setProperty("variant", "primary")
        self.add_button.setIcon(icons.icon("plus", "#FFFFFF", 15))
        self.add_button.setIconSize(QSize(14, 14))
        self.add_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.add_button.setFixedHeight(34)
        self.add_button.setStyleSheet("padding: 6px 12px; font-size: 11px;")
        self.add_button.clicked.connect(lambda: self.addRequested.emit(self._day))
        header.addWidget(self.add_button, 0, Qt.AlignmentFlag.AlignTop)

        self.task_button = QPushButton("Task")
        self.task_button.setProperty("variant", "secondary")
        self.task_button.setIcon(icons.icon("check-circle", accent_for(accent).color, 15))
        self.task_button.setIconSize(QSize(14, 14))
        self.task_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.task_button.setFixedHeight(34)
        self.task_button.setStyleSheet("padding: 6px 10px; font-size: 11px;")
        self.task_button.clicked.connect(lambda: self.taskRequested.emit(self._day))
        header.addWidget(self.task_button, 0, Qt.AlignmentFlag.AlignTop)
        outer.addLayout(header)
        outer.addWidget(make_divider())

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.viewport().setStyleSheet("background: transparent;")
        self.content = QWidget()
        self.content.setStyleSheet("background: transparent;")
        self.list_layout = QVBoxLayout(self.content)
        self.list_layout.setContentsMargins(0, 2, 2, 2)
        self.list_layout.setSpacing(8)
        self.scroll.setWidget(self.content)
        outer.addWidget(self.scroll, 1)

        footer = QLabel("Changes are saved automatically on this device.")
        footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        footer.setStyleSheet(f"color: {FAINT}; font-size: 9px;")
        outer.addWidget(footer)

        self.set_day(self._day, [])

    def set_accent(self, accent: str) -> None:
        self._accent = accent
        color = accent_for(accent).color
        self.kicker.setStyleSheet(
            f"color: {color}; font-size: 9px; font-weight: 800;"
        )
        self.task_button.setIcon(icons.icon("check-circle", color, 15))

    def set_day(
        self,
        day: date,
        events: list[Event],
        topics: list[TaskTopic] | None = None,
    ) -> None:
        self._day = day
        topics = topics or []
        today = date.today()
        difference = (day - today).days
        if difference == 0:
            kicker = "TODAY"
        elif difference == 1:
            kicker = "TOMORROW"
        else:
            kicker = weekday_name(day).upper()
        self.kicker.setText(kicker)
        self.title.setText(f"{day.day} {MONTH_NAMES[day.month - 1]}")
        count = len(events)
        self.subtitle.setText(
            f"{weekday_name(day)}, {day.year} · "
            f"{count} event{'s' if count != 1 else ''} · "
            f"{len(topics)} task{'s' if len(topics) != 1 else ''}"
        )
        self._clear()

        if topics:
            label = SectionLabel(
                f"{len(topics)} repeating task{'s' if len(topics) != 1 else ''}"
            )
            label.setContentsMargins(2, 2, 2, 2)
            self.list_layout.addWidget(label)
            for topic in topics:
                card = TaskTopicCard(topic, day)
                card.editRequested.connect(self.taskEditRequested)
                card.statusChanged.connect(self.progressChanged)
                card.percentChanged.connect(self.percentChanged)
                card.percentReset.connect(self.percentReset)
                self.list_layout.addWidget(card)

        if events:
            label = SectionLabel(
                f"{count} scheduled event{'s' if count != 1 else ''}"
            )
            label.setContentsMargins(2, 2, 2, 2)
            self.list_layout.addWidget(label)
            for event in events:
                card = EventCard(event)
                card.editRequested.connect(self.editRequested)
                card.deleteRequested.connect(self.deleteRequested)
                self.list_layout.addWidget(card)
        elif not topics:
            empty = EmptyState(
                "calendar",
                "Nothing booked",
                "This day is wide open. Add your first event to make it count.",
            )
            self.list_layout.addWidget(empty)

        self.list_layout.addStretch(1)

    def _clear(self) -> None:
        while self.list_layout.count():
            item = self.list_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
