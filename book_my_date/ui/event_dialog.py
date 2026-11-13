"""Create and edit event dialog."""

from __future__ import annotations

from datetime import date, datetime, time

from PySide6.QtCore import QDate, QSize, Qt, QTime, Signal
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
    QTextEdit,
    QTimeEdit,
    QVBoxLayout,
    QWidget,
)

from ..core.models import (
    CATEGORIES,
    DEFAULT_CATEGORY,
    DEFAULT_REMINDER_MINUTES,
    MAX_DESCRIPTION_LENGTH,
    Event,
    ValidationError,
    reminder_label,
)
from . import icons
from .theme import FAINT, MUTED, accent_for
from .widgets import IconButton, make_divider


class EventDialog(QDialog):
    deleteRequested = Signal(object)

    def __init__(
        self,
        *,
        selected_date: date,
        accent: str = "indigo",
        default_reminder: int = DEFAULT_REMINDER_MINUTES,
        event: Event | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._accent = accent_for(accent)
        self._original = event
        self._result: Event | None = None
        self._deleted = False
        self.setObjectName("EventDialog")
        self.setWindowTitle("Edit event · Book My Date" if event else "New event · Book My Date")
        self.setModal(True)
        self.resize(590, 760)
        self.setMinimumSize(540, 640)

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
        title = QLabel("Edit event" if event else "New event")
        title.setObjectName("DialogTitle")
        heading.addWidget(title)
        subtitle = QLabel(
            "Update the details below."
            if event
            else "Plan something worth remembering — it only takes a moment."
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
        holder_layout.setSpacing(0)
        form_card = QFrame()
        form_card.setObjectName("Card")
        form = QVBoxLayout(form_card)
        form.setContentsMargins(20, 18, 20, 20)
        form.setSpacing(14)
        holder_layout.addWidget(form_card)
        holder_layout.addStretch(1)
        scroll.setWidget(holder)

        start_day = event.start_at.date() if event else selected_date
        end_day = event.end_at.date() if event else start_day
        start_clock = (
            event.start_at.time().replace(tzinfo=None)
            if event and not event.all_day
            else time(9, 0)
        )
        end_clock = (
            event.end_at.time().replace(tzinfo=None)
            if event and not event.all_day
            else time(10, 0)
        )

        self.title_input = QLineEdit(event.title if event else "")
        self.title_input.setMaxLength(120)
        self.title_input.setPlaceholderText("e.g. Product design review")
        self.title_input.setClearButtonEnabled(True)
        form.addWidget(self._field("Event title", self.title_input))

        self.start_date = self._date_edit(start_day)
        self.end_date = self._date_edit(end_day)
        date_row = QHBoxLayout()
        date_row.setSpacing(12)
        date_row.addWidget(self._field("Starts", self.start_date), 1)
        date_row.addWidget(self._field("Ends", self.end_date), 1)
        form.addLayout(date_row)

        self.all_day = QCheckBox("All-day event")
        self.all_day.setChecked(bool(event and event.all_day))
        form.addWidget(self.all_day)

        self.start_time = QTimeEdit()
        self.start_time.setDisplayFormat("HH:mm")
        self.start_time.setTime(QTime(start_clock.hour, start_clock.minute))
        self.start_time.setWrapping(True)
        self.end_time = QTimeEdit()
        self.end_time.setDisplayFormat("HH:mm")
        self.end_time.setTime(QTime(end_clock.hour, end_clock.minute))
        self.end_time.setWrapping(True)

        self.time_row = QWidget()
        time_row_layout = QHBoxLayout(self.time_row)
        time_row_layout.setContentsMargins(0, 0, 0, 0)
        time_row_layout.setSpacing(12)
        time_row_layout.addWidget(self._field("Start time", self.start_time), 1)
        time_row_layout.addWidget(self._field("End time", self.end_time), 1)
        form.addWidget(self.time_row)

        self.location_input = QLineEdit(event.location if event else "")
        self.location_input.setMaxLength(160)
        self.location_input.setPlaceholderText("Optional — room, address or video link")
        form.addWidget(self._field("Location", self.location_input))

        self.category = QComboBox()
        self.category.setIconSize(QSize(12, 12))
        for key, meta in CATEGORIES.items():
            self.category.addItem(icons.dot(meta.color, 10), meta.label, key)
        selected_category = event.category if event else DEFAULT_CATEGORY
        index = self.category.findData(selected_category)
        self.category.setCurrentIndex(max(0, index))
        form.addWidget(self._field("Category", self.category))

        self.reminder = QComboBox()
        for minutes, label in (
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
        ):
            self.reminder.addItem(label, -1 if minutes is None else minutes)
        reminder_value = (
            event.reminder_minutes
            if event is not None
            else default_reminder
        )
        reminder_index = self.reminder.findData(
            -1 if reminder_value is None else int(reminder_value)
        )
        self.reminder.setCurrentIndex(max(0, reminder_index))
        form.addWidget(self._field("Reminder", self.reminder))

        self.reminder_hint = QLabel("")
        self.reminder_hint.setStyleSheet(f"color: {FAINT}; font-size: 10px;")
        form.addWidget(self.reminder_hint)

        self.description = QTextEdit()
        self.description.setAcceptRichText(False)
        self.description.setPlaceholderText(
            "Add agenda, notes, links or anything you want to remember…"
        )
        self.description.setFixedHeight(112)
        self.description.setPlainText(event.description if event else "")
        form.addWidget(self._field("Description", self.description))

        description_footer = QHBoxLayout()
        description_footer.setContentsMargins(0, 0, 0, 0)
        self.counter = QLabel("")
        self.counter.setStyleSheet(f"color: {FAINT}; font-size: 10px;")
        description_footer.addStretch(1)
        description_footer.addWidget(self.counter)
        form.addLayout(description_footer)

        root.addWidget(make_divider())
        footer = QHBoxLayout()
        footer.setSpacing(8)
        if event is not None:
            delete = QPushButton("Delete event")
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
        self.save_button = QPushButton("Save changes" if event else "Create event")
        self.save_button.setProperty("variant", "primary")
        self.save_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.save_button.setDefault(True)
        self.save_button.clicked.connect(self._on_save)
        footer.addWidget(self.save_button)
        root.addLayout(footer)

        self.all_day.toggled.connect(self._sync_all_day)
        self.start_date.dateChanged.connect(self._sync_dates)
        self.start_time.timeChanged.connect(self._sync_times)
        self.reminder.currentIndexChanged.connect(self._update_reminder_hint)
        self.description.textChanged.connect(self._update_counter)
        save_shortcut = QShortcut(QKeySequence("Ctrl+Return"), self)
        save_shortcut.activated.connect(self._on_save)
        enter_shortcut = QShortcut(QKeySequence("Ctrl+Enter"), self)
        enter_shortcut.activated.connect(self._on_save)

        self._sync_all_day(self.all_day.isChecked())
        self._update_counter()
        self._update_reminder_hint()
        if event is None:
            self.title_input.setFocus()

    # ------------------------------------------------------------------ public
    def created_event(self) -> Event | None:
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

    def _sync_all_day(self, checked: bool) -> None:
        self.time_row.setVisible(not checked)
        if checked:
            self.end_date.setMinimumDate(self.start_date.date())
        self._update_reminder_hint()

    def _sync_dates(self, _value: QDate) -> None:
        self.end_date.setMinimumDate(self.start_date.date())
        if self.end_date.date() < self.start_date.date():
            self.end_date.setDate(self.start_date.date())
        self._update_reminder_hint()

    def _sync_times(self, _value: QTime) -> None:
        if self.all_day.isChecked():
            return
        if self.end_time.time() <= self.start_time.time():
            start = self.start_time.time()
            candidate = start.addSecs(3600)
            if candidate <= start:
                candidate = QTime(23, 59)
            self.end_time.setTime(candidate)
        self._update_reminder_hint()

    def _update_counter(self) -> None:
        text = self.description.toPlainText()
        if len(text) > MAX_DESCRIPTION_LENGTH:
            cursor = self.description.textCursor()
            position = cursor.position()
            self.description.blockSignals(True)
            self.description.setPlainText(text[:MAX_DESCRIPTION_LENGTH])
            cursor.setPosition(min(position, MAX_DESCRIPTION_LENGTH))
            self.description.setTextCursor(cursor)
            self.description.blockSignals(False)
            text = text[:MAX_DESCRIPTION_LENGTH]
        self.counter.setText(f"{len(text):,} / {MAX_DESCRIPTION_LENGTH:,}")

    def _selected_reminder_minutes(self) -> int | None:
        value = self.reminder.currentData()
        if value is None or int(value) < 0:
            return None
        return int(value)

    def _build_event(self) -> Event:
        start_day = self.start_date.date().toPython()
        end_day = self.end_date.date().toPython()
        if self.all_day.isChecked():
            start_at = datetime.combine(start_day, time.min)
            end_at = datetime.combine(end_day, time(23, 59, 59))
        else:
            start_at = datetime.combine(
                start_day,
                time(self.start_time.time().hour(), self.start_time.time().minute()),
            )
            end_at = datetime.combine(
                end_day,
                time(self.end_time.time().hour(), self.end_time.time().minute()),
            )
        original = self._original
        return Event(
            id=original.id if original else None,
            title=self.title_input.text(),
            description=self.description.toPlainText(),
            location=self.location_input.text(),
            start_at=start_at,
            end_at=end_at,
            all_day=self.all_day.isChecked(),
            category=str(self.category.currentData() or DEFAULT_CATEGORY),
            reminder_minutes=self._selected_reminder_minutes(),
            notified=original.notified if original else False,
            created_at=original.created_at if original else None,
            updated_at=original.updated_at if original else None,
        )

    def _update_reminder_hint(self) -> None:
        try:
            candidate = self._build_event()
        except ValidationError:
            self.reminder_hint.setText("")
            return
        moment = candidate.reminder_at
        if moment is None:
            self.reminder_hint.setText("No notification will be sent.")
            return
        self.reminder_hint.setText(
            f"{reminder_label(candidate.reminder_minutes)} · "
            f"{moment.strftime('%a %d %b at %H:%M')}"
        )

    def _show_error(self, message: str) -> None:
        self.error.setText(message)
        self.error.show()

    def _on_save(self) -> None:
        self.error.hide()
        try:
            result = self._build_event()
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
            "Delete event?",
            f"“{self._original.title}” will be permanently deleted.",
            QMessageBox.StandardButton.Delete | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if answer == QMessageBox.StandardButton.Delete:
            self._deleted = True
            self.deleteRequested.emit(self._original)
            self.accept()
