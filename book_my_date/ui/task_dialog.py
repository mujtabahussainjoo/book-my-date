"""Create and edit repeating task topics with multiple subtasks."""

from __future__ import annotations

from datetime import date, timedelta

from PySide6.QtCore import QDate, QSize, Qt, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ..core.models import (
    DEFAULT_SUBTASK_COLOR,
    MAX_SUBTASK_TITLE_LENGTH,
    MAX_SUBTASKS_PER_TOPIC,
    MAX_TOPIC_TITLE_LENGTH,
    PROGRESS_STATUSES,
    STATUS_LABELS,
    SUBTASK_COLORS,
    WEEKDAY_INITIALS,
    Subtask,
    TaskTopic,
    ValidationError,
)
from . import icons
from .theme import FAINT, MUTED, accent_for
from .widgets import IconButton, SectionLabel, make_divider


class _SubtaskEditRow(QFrame):
    removeRequested = Signal(object)

    def __init__(self, subtask: Subtask | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("SoftCard")
        self._original = subtask
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 7, 8, 7)
        layout.setSpacing(8)

        self.title_input = QLineEdit(subtask.title if subtask else "")
        self.title_input.setMaxLength(MAX_SUBTASK_TITLE_LENGTH)
        self.title_input.setPlaceholderText("e.g. Drink a glass of water")
        self.title_input.setClearButtonEnabled(True)
        layout.addWidget(self.title_input, 1)

        self.color = QComboBox()
        self.color.setFixedWidth(126)
        self.color.setIconSize(QSize(10, 10))
        for key, meta in SUBTASK_COLORS.items():
            self.color.addItem(icons.dot(meta.color, 10), meta.label, key)
        color_key = subtask.color if subtask else DEFAULT_SUBTASK_COLOR
        self.color.setCurrentIndex(max(0, self.color.findData(color_key)))
        layout.addWidget(self.color, 0)

        remove = IconButton("trash", size=28, icon_size=14, color="#DC2626", tooltip="Remove subtask")
        remove.clicked.connect(lambda: self.removeRequested.emit(self))
        layout.addWidget(remove, 0)

    def to_subtask(self) -> Subtask:
        return Subtask(
            id=self._original.id if self._original else None,
            title=self.title_input.text(),
            color=str(self.color.currentData() or DEFAULT_SUBTASK_COLOR),
            position=self._original.position if self._original else 0,
        )


class TaskDialog(QDialog):
    def __init__(
        self,
        *,
        selected_date: date,
        accent: str = "indigo",
        topic: TaskTopic | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._accent = accent_for(accent)
        self._original = topic
        self._result: TaskTopic | None = None
        self._deleted = False
        self._rows: list[_SubtaskEditRow] = []
        self.setObjectName("TaskDialog")
        self.setWindowTitle("Edit task topic · Book My Date" if topic else "New task topic · Book My Date")
        self.setModal(True)
        self.resize(620, 720)
        self.setMinimumSize(560, 620)

        root = QVBoxLayout(self)
        root.setContentsMargins(22, 18, 22, 16)
        root.setSpacing(12)

        header = QHBoxLayout()
        header.setSpacing(12)
        logo = QLabel()
        logo.setFixedSize(46, 46)
        logo.setPixmap(icons.logo_pixmap(46))
        header.addWidget(logo, 0, Qt.AlignmentFlag.AlignTop)
        heading = QVBoxLayout()
        heading.setSpacing(1)
        title = QLabel("Edit task topic" if topic else "New task topic")
        title.setObjectName("DialogTitle")
        heading.addWidget(title)
        subtitle = QLabel(
            "Group subtasks into a repeatable achievement tracker."
        )
        subtitle.setStyleSheet(f"color: {MUTED}; font-size: 11px;")
        heading.addWidget(subtitle)
        header.addLayout(heading, 1)
        close = IconButton("close", size=32, icon_size=15, tooltip="Close")
        close.clicked.connect(self.reject)
        header.addWidget(close, 0, Qt.AlignmentFlag.AlignTop)
        root.addLayout(header)

        self.error = QLabel()
        self.error.setObjectName("ErrorBanner")
        self.error.setWordWrap(True)
        self.error.hide()
        root.addWidget(self.error)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.viewport().setStyleSheet("background: transparent;")
        root.addWidget(scroll, 1)

        holder = QWidget()
        holder.setStyleSheet("background: transparent;")
        holder_layout = QVBoxLayout(holder)
        holder_layout.setContentsMargins(0, 0, 4, 0)
        holder_layout.setSpacing(12)
        form_card = QFrame()
        form_card.setObjectName("Card")
        form = QVBoxLayout(form_card)
        form.setContentsMargins(20, 18, 20, 20)
        form.setSpacing(14)
        holder_layout.addWidget(form_card)

        self.title_input = QLineEdit(topic.title if topic else "")
        self.title_input.setMaxLength(MAX_TOPIC_TITLE_LENGTH)
        self.title_input.setPlaceholderText("e.g. Morning routine")
        self.title_input.setClearButtonEnabled(True)
        form.addWidget(self._field("Task topic", self.title_input))

        self.apply_all = QCheckBox("Apply automatically to every calendar date")
        self.apply_all.setChecked(bool(topic.apply_to_all_dates) if topic else True)
        form.addWidget(self.apply_all)

        self.schedule = QWidget()
        self.schedule.setStyleSheet("background: transparent;")
        schedule_layout = QVBoxLayout(self.schedule)
        schedule_layout.setContentsMargins(0, 0, 0, 0)
        schedule_layout.setSpacing(10)
        self.start_date = self._date_edit(
            topic.start_date if topic else selected_date
        )
        self.end_date = self._date_edit(
            topic.end_date
            if topic and topic.end_date
            else (selected_date + timedelta(days=30))
        )
        dates = QHBoxLayout()
        dates.setSpacing(12)
        dates.addWidget(self._field("Starts", self.start_date), 1)
        dates.addWidget(self._field("Ends", self.end_date), 1)
        schedule_layout.addLayout(dates)

        self.no_end = QCheckBox("No end date")
        self.no_end.setChecked(not (topic and topic.end_date))
        schedule_layout.addWidget(self.no_end)

        weekdays_label = QLabel("Active weekdays")
        weekdays_label.setObjectName("FieldLabel")
        schedule_layout.addWidget(weekdays_label)
        weekday_row = QHBoxLayout()
        weekday_row.setContentsMargins(0, 0, 0, 0)
        weekday_row.setSpacing(5)
        self.weekday_boxes: list[QCheckBox] = []
        selected_days = topic.weekday_list() if topic else list(range(7))
        for index, initial in enumerate(WEEKDAY_INITIALS):
            check = QCheckBox(initial)
            check.setChecked(index in selected_days)
            check.setToolTip(
                ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")[index]
            )
            self.weekday_boxes.append(check)
            weekday_row.addWidget(check)
        weekday_row.addStretch(1)
        schedule_layout.addLayout(weekday_row)
        self.start_date.dateChanged.connect(self._sync_dates)
        self.no_end.toggled.connect(self._sync_schedule)
        self.apply_all.toggled.connect(self._sync_schedule)
        form.addWidget(self.schedule)

        form.addWidget(make_divider())
        section = SectionLabel("Subtasks")
        section.setContentsMargins(0, 0, 0, 0)
        form.addWidget(section)

        self.subtasks_layout = QVBoxLayout()
        self.subtasks_layout.setContentsMargins(0, 0, 0, 0)
        self.subtasks_layout.setSpacing(8)
        form.addLayout(self.subtasks_layout)

        self.add_subtask = QPushButton("  Add subtask")
        self.add_subtask.setProperty("variant", "secondary")
        self.add_subtask.setIcon(icons.icon("plus", self._accent.color, 15))
        self.add_subtask.setIconSize(QSize(14, 14))
        self.add_subtask.setCursor(Qt.CursorShape.PointingHandCursor)
        self.add_subtask.clicked.connect(lambda: self._append_subtask())
        form.addWidget(self.add_subtask)

        self.preview = QLabel("")
        self.preview.setStyleSheet(f"color: {FAINT}; font-size: 10px;")
        form.addWidget(self.preview)

        legend = QLabel("  ·  ".join(
            f"{value}% {STATUS_LABELS[value]}" for value in PROGRESS_STATUSES
        ))
        legend.setWordWrap(True)
        legend.setStyleSheet(f"color: {FAINT}; font-size: 9px;")
        form.addWidget(legend)

        holder_layout.addStretch(1)
        scroll.setWidget(holder)

        root.addWidget(make_divider())
        footer = QHBoxLayout()
        footer.setSpacing(8)
        if topic is not None:
            delete = QPushButton("Delete topic")
            delete.setProperty("variant", "danger")
            delete.setCursor(Qt.CursorShape.PointingHandCursor)
            delete.clicked.connect(self._confirm_delete)
            footer.addWidget(delete)
        footer.addStretch(1)
        cancel = QPushButton("Cancel")
        cancel.setProperty("variant", "secondary")
        cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel.clicked.connect(self.reject)
        footer.addWidget(cancel)
        self.save_button = QPushButton("Save changes" if topic else "Create task topic")
        self.save_button.setProperty("variant", "primary")
        self.save_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.save_button.setDefault(True)
        self.save_button.clicked.connect(self._on_save)
        footer.addWidget(self.save_button)
        root.addLayout(footer)

        if topic is not None:
            for subtask in topic.subtasks:
                self._append_subtask(subtask)
        else:
            self._append_subtask()
        self._sync_schedule()
        self._sync_dates()
        self._update_preview()
        save_shortcut = QShortcut(QKeySequence("Ctrl+Return"), self)
        save_shortcut.activated.connect(self._on_save)
        enter_shortcut = QShortcut(QKeySequence("Ctrl+Enter"), self)
        enter_shortcut.activated.connect(self._on_save)
        if topic is None:
            self.title_input.setFocus()

    # ------------------------------------------------------------------ public
    def created_topic(self) -> TaskTopic | None:
        return self._result

    @property
    def deleted(self) -> bool:
        return self._deleted

    # ------------------------------------------------------------------ helpers
    def _field(self, label_text: str, widget: QWidget) -> QWidget:
        wrapper = QWidget()
        wrapper.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        layout = QVBoxLayout(wrapper)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
        label = QLabel(label_text)
        label.setObjectName("FieldLabel")
        layout.addWidget(label)
        layout.addWidget(widget)
        return wrapper

    @staticmethod
    def _date_edit(day: date) -> QDateEdit:
        edit = QDateEdit()
        edit.setCalendarPopup(True)
        edit.setDisplayFormat("ddd, dd MMM yyyy")
        edit.setMinimumDate(QDate(1900, 1, 1))
        edit.setMaximumDate(QDate(2100, 12, 31))
        edit.setDate(QDate(day.year, day.month, day.day))
        return edit

    def _append_subtask(self, subtask: Subtask | None = None) -> None:
        if len(self._rows) >= MAX_SUBTASKS_PER_TOPIC:
            self._show_error(
                f"A task topic can have at most {MAX_SUBTASKS_PER_TOPIC} subtasks."
            )
            return
        row = _SubtaskEditRow(subtask, self)
        row.removeRequested.connect(self._remove_subtask)
        self._rows.append(row)
        self.subtasks_layout.addWidget(row)
        self._update_preview()
        if subtask is None:
            row.title_input.setFocus()

    def _remove_subtask(self, row: _SubtaskEditRow) -> None:
        if row not in self._rows:
            return
        self._rows.remove(row)
        self.subtasks_layout.removeWidget(row)
        row.deleteLater()
        self._update_preview()

    def _sync_schedule(self) -> None:
        limited = not self.apply_all.isChecked()
        self.schedule.setEnabled(limited)
        self.end_date.setEnabled(limited and not self.no_end.isChecked())

    def _sync_dates(self, _value: QDate | None = None) -> None:
        if self.end_date.date() < self.start_date.date():
            self.end_date.setDate(self.start_date.date())

    def _update_preview(self) -> None:
        count = len(self._rows)
        self.preview.setText(
            f"{count} subtask{'s' if count != 1 else ''} · each date starts at 0% "
            "and is tracked separately."
        )

    def _build_topic(self) -> TaskTopic:
        original = self._original
        apply_all = self.apply_all.isChecked()
        end = (
            None
            if apply_all or self.no_end.isChecked()
            else self.end_date.date().toPython()
        )
        weekdays = frozenset(
            index
            for index, check in enumerate(self.weekday_boxes)
            if check.isChecked()
        )
        return TaskTopic(
            id=original.id if original else None,
            title=self.title_input.text(),
            subtasks=[row.to_subtask() for row in self._rows],
            apply_to_all_dates=apply_all,
            start_date=self.start_date.date().toPython(),
            end_date=end,
            weekdays=weekdays,
            created_at=original.created_at if original else None,
            updated_at=original.updated_at if original else None,
        )

    def _show_error(self, message: str) -> None:
        self.error.setText(message)
        self.error.show()

    def _on_save(self) -> None:
        self.error.hide()
        if not self._rows:
            self._show_error("Add at least one subtask to this task topic.")
            return
        try:
            result = self._build_topic()
        except ValidationError as exc:
            self._show_error(str(exc))
            return
        self._result = result
        self.accept()

    def _confirm_delete(self) -> None:
        if self._original is None:
            return
        answer = QMessageBox.question(
            self,
            "Delete task topic?",
            f"“{self._original.title}” and all of its saved daily progress "
            "will be permanently deleted.",
            QMessageBox.StandardButton.Delete | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if answer == QMessageBox.StandardButton.Delete:
            self._deleted = True
            self.accept()
