"""Reusable widgets for repeating task topics and their daily progress."""

from __future__ import annotations

from datetime import date

from PySide6.QtCore import QEvent, QSignalBlocker, Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ..core.models import (
    PROGRESS_STATUSES,
    STATUS_COLORS,
    STATUS_LABELS,
    STATUS_SOFT_COLORS,
    Subtask,
    TaskTopic,
    completion_color,
    completion_soft_color,
    status_color,
)
from . import icons
from .theme import FAINT, INK, MUTED
from .widgets import ElidedLabel, IconButton, make_divider


class ProgressBar(QFrame):
    """A slim coloured bar used for both topics and individual subtasks."""

    def __init__(
        self,
        percent: int = 0,
        color: str = STATUS_COLORS[0],
        *,
        height: int = 8,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("TaskProgressTrack")
        self.setFixedHeight(height)
        self._percent = 0
        self._color = color
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self._fill = QFrame(self)
        self._fill.setObjectName("TaskProgressFill")
        layout.addWidget(self._fill, 0)
        layout.addStretch(1)
        self.set_value(percent, color)

    def set_value(self, percent: int, color: str | None = None) -> None:
        self._percent = max(0, min(100, int(percent)))
        if color is not None:
            self._color = color
        self.setStyleSheet(
            "QFrame#TaskProgressTrack { background: #E9EDF5; border-radius: 4px; }"
        )
        self._fill.setStyleSheet(
            "QFrame#TaskProgressFill {"
            f"background: {self._color}; border-radius: 4px;"
            "}"
        )
        self._apply_width()

    def _apply_width(self) -> None:
        self._fill.setFixedWidth(int(self.width() * self._percent / 100))
        self._fill.setVisible(self._percent > 0)

    def resizeEvent(self, event: QEvent) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._apply_width()


class TopicChip(QFrame):
    clicked = Signal(object)

    def __init__(
        self,
        topic: TaskTopic,
        day: date | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._topic = topic
        percent = topic.completion_for(day)
        color = completion_color(percent)
        soft = completion_soft_color(percent)
        self.setObjectName("TaskChip")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(21)
        self.setToolTip(f"{topic.title}\n{percent}% complete · {topic.schedule_label()}")
        self.setStyleSheet(
            "QFrame#TaskChip {"
            f"background: {soft}; border: 1px solid {color}; border-radius: 5px;"
            "}"
        )
        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 1, 6, 1)
        layout.setSpacing(4)
        dot = QLabel()
        dot.setPixmap(icons.dot(color, 7).pixmap(7, 7))
        dot.setFixedSize(7, 7)
        layout.addWidget(dot, 0, Qt.AlignmentFlag.AlignVCenter)
        title = ElidedLabel(topic.title)
        title.setStyleSheet(
            f"color: {INK}; font-size: 9px; font-weight: 700; background: transparent;"
        )
        layout.addWidget(title, 1, Qt.AlignmentFlag.AlignVCenter)
        amount = QLabel(f"{percent}%")
        amount.setStyleSheet(
            f"color: {color}; font-size: 9px; font-weight: 800; background: transparent;"
        )
        layout.addWidget(amount, 0, Qt.AlignmentFlag.AlignVCenter)

    def mouseReleaseEvent(self, event: QEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self._topic)
        super().mouseReleaseEvent(event)


class SubtaskRow(QFrame):
    statusChanged = Signal(int, int)

    def __init__(
        self,
        subtask: Subtask,
        status: int = 0,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._subtask = subtask
        self.setObjectName("SubtaskRow")
        self.setStyleSheet(
            "QFrame#SubtaskRow { background: transparent; border: none; }"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setSpacing(4)

        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(6)
        dot = QLabel()
        dot.setPixmap(icons.dot(subtask.meta.color, 7).pixmap(7, 7))
        dot.setFixedSize(7, 7)
        top.addWidget(dot, 0, Qt.AlignmentFlag.AlignVCenter)
        title = ElidedLabel(subtask.title)
        title.setStyleSheet(f"color: {INK}; font-size: 11px; font-weight: 600;")
        top.addWidget(title, 1, Qt.AlignmentFlag.AlignVCenter)

        self.percent = QLabel(f"{status}%")
        self.percent.setFixedWidth(36)
        self.percent.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.percent.setStyleSheet(
            f"color: {status_color(status)}; font-size: 10px; font-weight: 800;"
        )
        top.addWidget(self.percent, 0, Qt.AlignmentFlag.AlignVCenter)
        layout.addLayout(top)

        status_row = QHBoxLayout()
        status_row.setContentsMargins(0, 0, 0, 0)
        status_row.setSpacing(4)
        status_label = QLabel("STATUS")
        status_label.setStyleSheet(
            f"color: {MUTED}; font-size: 8px; font-weight: 800; letter-spacing: 1px;"
        )
        status_row.addWidget(status_label, 0, Qt.AlignmentFlag.AlignVCenter)
        status_row.addSpacing(2)
        self.status_buttons: dict[int, QPushButton] = {}
        for value in PROGRESS_STATUSES:
            button = QPushButton(f"{value}%", self)
            button.setObjectName("TaskStatusButton")
            button.setCheckable(True)
            button.setAutoExclusive(True)
            button.setFixedSize(38, 24)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setToolTip(f"{value}% · {STATUS_LABELS[value]}")
            button.clicked.connect(
                lambda _checked=False, selected=value: self._select(selected)
            )
            status_row.addWidget(button, 0, Qt.AlignmentFlag.AlignVCenter)
            self.status_buttons[value] = button
        status_row.addStretch(1)
        layout.addLayout(status_row)
        self.setToolTip("Click a status to set today's progress for this subtask")
        if subtask.id is None:
            for button in self.status_buttons.values():
                button.setEnabled(False)

        self.bar = ProgressBar(status, subtask.meta.color, height=6)
        layout.addWidget(self.bar)
        self._apply_status(status)

    def _apply_status(self, status: int) -> None:
        self.percent.setText(f"{status}%")
        self.percent.setStyleSheet(
            f"color: {status_color(status)}; font-size: 10px; font-weight: 800;"
        )
        self.bar.set_value(status)
        for value, button in self.status_buttons.items():
            active = value == status
            button.setChecked(active)
            color = STATUS_COLORS[value]
            background = color if active else STATUS_SOFT_COLORS[value]
            foreground = "#FFFFFF" if active else MUTED
            button.setStyleSheet(
                "QPushButton#TaskStatusButton {"
                f"background: {background}; color: {foreground};"
                f"border: 1px solid {color}; border-radius: 5px;"
                "font-size: 8px; font-weight: 800; padding: 0px;"
                "}"
            )

    def _select(self, status: int) -> None:
        value = int(status)
        self._apply_status(value)
        if self._subtask.id is not None:
            self.statusChanged.emit(self._subtask.id, value)


class TaskTopicCard(QFrame):
    editRequested = Signal(object)
    statusChanged = Signal(int, int, int)
    percentChanged = Signal(int, int)
    percentReset = Signal(int)

    def __init__(
        self,
        topic: TaskTopic,
        day: date | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._topic = topic
        self._day = day
        percent = topic.completion_for(day)
        color = completion_color(percent)
        self.setObjectName("TaskCard")
        self.setStyleSheet(
            "QFrame#TaskCard {"
            "background: #FFFFFF; border: 1px solid #E5E9F2; border-radius: 13px;"
            "}"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(7)
        self.setToolTip(topic.schedule_label())

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(6)
        self.kicker = QLabel("REPEATING TASK")
        self.kicker.setStyleSheet(
            f"color: {color}; font-size: 8px; font-weight: 800; letter-spacing: 1px;"
        )
        header.addWidget(self.kicker, 0, Qt.AlignmentFlag.AlignVCenter)
        header.addStretch(1)
        self.total = QLabel(f"{percent}% complete")
        self.total.setStyleSheet(f"color: {color}; font-size: 10px; font-weight: 800;")
        header.addWidget(self.total, 0, Qt.AlignmentFlag.AlignVCenter)
        edit = IconButton("edit", size=24, icon_size=12, tooltip="Edit task topic")
        edit.clicked.connect(lambda: self.editRequested.emit(self._topic))
        header.addWidget(edit, 0, Qt.AlignmentFlag.AlignVCenter)
        layout.addLayout(header)

        title = QLabel(topic.title)
        title.setWordWrap(True)
        title.setStyleSheet(f"color: {INK}; font-size: 13px; font-weight: 700;")
        layout.addWidget(title)

        schedule = QLabel(topic.schedule_label())
        schedule.setStyleSheet(f"color: {FAINT}; font-size: 9px;")
        layout.addWidget(schedule)

        progress_row = QHBoxLayout()
        progress_row.setContentsMargins(0, 0, 0, 0)
        progress_row.setSpacing(6)
        percent_label = QLabel("Overall completion")
        percent_label.setStyleSheet(f"color: {MUTED}; font-size: 10px;")
        progress_row.addWidget(percent_label, 0, Qt.AlignmentFlag.AlignVCenter)
        self.percent_spin = QSpinBox()
        self.percent_spin.setRange(0, 100)
        self.percent_spin.setSingleStep(5)
        self.percent_spin.setSuffix(" %")
        self.percent_spin.setFixedWidth(78)
        self.percent_spin.setToolTip(
            "Set the overall completion for this date. "
            "Subtask progress is used until you enter a percent."
        )
        self.percent_spin.setValue(percent)
        self.percent_spin.valueChanged.connect(self._on_percent_changed)
        progress_row.addWidget(self.percent_spin, 0, Qt.AlignmentFlag.AlignVCenter)
        self.auto_button = QPushButton("Auto")
        self.auto_button.setProperty("variant", "secondary")
        self.auto_button.setFixedHeight(24)
        self.auto_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.auto_button.setToolTip("Use the subtask average instead of a fixed percent")
        self.auto_button.setVisible(
            bool(day is not None and topic.has_manual_progress(day))
        )
        self.auto_button.clicked.connect(self._reset_percent)
        progress_row.addWidget(self.auto_button, 0, Qt.AlignmentFlag.AlignVCenter)
        progress_row.addStretch(1)
        layout.addLayout(progress_row)

        self.bar = ProgressBar(percent, color)
        layout.addWidget(self.bar)

        completed = QLabel(
            f"{topic.completed_count()} of {len(topic.subtasks)} subtasks complete"
        )
        completed.setStyleSheet(f"color: {MUTED}; font-size: 9px;")
        layout.addWidget(completed)

        if topic.subtasks:
            layout.addWidget(make_divider())
            for subtask in topic.subtasks:
                row = SubtaskRow(subtask, topic.status_for(subtask.id))
                row.statusChanged.connect(
                    lambda child_id, status, item=topic: self.statusChanged.emit(
                        item.id or 0, child_id, status
                    )
                )
                layout.addWidget(row)

    def _apply_percent(self, percent: int) -> None:
        color = completion_color(percent)
        self.kicker.setStyleSheet(
            f"color: {color}; font-size: 8px; font-weight: 800; letter-spacing: 1px;"
        )
        self.total.setText(f"{percent}% complete")
        self.total.setStyleSheet(
            f"color: {color}; font-size: 10px; font-weight: 800;"
        )
        self.bar.set_value(percent, color)

    def _on_percent_changed(self, value: int) -> None:
        self._apply_percent(int(value))
        self.auto_button.setVisible(True)
        if self._topic.id is not None:
            self.percentChanged.emit(self._topic.id, int(value))

    def _reset_percent(self) -> None:
        derived = self._topic.completion()
        with QSignalBlocker(self.percent_spin):
            self.percent_spin.setValue(derived)
        self._apply_percent(derived)
        self.auto_button.setVisible(False)
        if self._topic.id is not None:
            self.percentReset.emit(self._topic.id)
