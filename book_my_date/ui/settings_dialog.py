"""Preferences, data tools and about panel."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QSize, Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ..config import APP_NAME, VERSION, app_data_dir
from ..core.database import Database
from ..core.models import REMINDER_CHOICES
from . import icons
from .theme import ACCENTS, FAINT, INK, MUTED, accent_for
from .widgets import IconButton, make_divider


def _human_size(size: int) -> str:
    value = float(size)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            return f"{value:.1f} {unit}" if unit != "B" else f"{int(value)} B"
        value /= 1024
    return f"{value:.1f} GB"


class SettingsDialog(QDialog):
    settingsSaved = Signal(dict)

    def __init__(
        self,
        database: Database,
        *,
        accent: str = "indigo",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.database = database
        self._accent = accent
        self.setObjectName("SettingsDialog")
        self.setWindowTitle(f"Settings · {APP_NAME}")
        self.setModal(True)
        self.resize(580, 760)
        self.setMinimumSize(520, 620)

        root = QVBoxLayout(self)
        root.setContentsMargins(22, 18, 22, 16)
        root.setSpacing(12)

        header = QHBoxLayout()
        header.setSpacing(12)
        gear = QLabel()
        gear.setFixedSize(42, 42)
        gear.setAlignment(Qt.AlignmentFlag.AlignCenter)
        gear.setPixmap(icons.icon("settings", accent_for(accent).color, 21).pixmap(21, 21))
        gear.setStyleSheet(
            f"background: {accent_for(accent).soft}; border-radius: 21px;"
        )
        header.addWidget(gear)
        titles = QVBoxLayout()
        titles.setSpacing(0)
        title = QLabel("Settings")
        title.setObjectName("DialogTitle")
        titles.addWidget(title)
        subtitle = QLabel("Make Book My Date feel like yours.")
        subtitle.setStyleSheet(f"color: {MUTED}; font-size: 11px;")
        titles.addWidget(subtitle)
        header.addLayout(titles, 1)
        close = IconButton("close", size=32, icon_size=15, tooltip="Close")
        close.clicked.connect(self.reject)
        header.addWidget(close, 0, Qt.AlignmentFlag.AlignTop)
        root.addLayout(header)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.viewport().setStyleSheet("background: transparent;")
        root.addWidget(scroll, 1)

        holder = QWidget()
        holder.setStyleSheet("background: transparent;")
        content = QVBoxLayout(holder)
        content.setContentsMargins(0, 0, 4, 0)
        content.setSpacing(12)
        self._content_layout = content
        scroll.setWidget(holder)

        # Appearance ---------------------------------------------------------
        appearance = self._section(
            "Appearance", "Choose how your calendar looks and flows."
        )
        self.week_start = QComboBox()
        self.week_start.addItem("Monday", 0)
        self.week_start.addItem("Sunday", 6)
        week_value = database.get_int("week_start", 0)
        self.week_start.setCurrentIndex(
            max(0, self.week_start.findData(6 if week_value not in (0, 6) else week_value))
        )
        appearance.addWidget(
            self._row("Week starts on", "The first column of every calendar.", self.week_start)
        )

        accent_label = QLabel("Accent color")
        accent_label.setObjectName("FieldLabel")
        appearance.addWidget(accent_label)
        accents = QHBoxLayout()
        accents.setSpacing(8)
        self.accent_group = QButtonGroup(self)
        self.accent_group.setExclusive(True)
        current_accent = database.get_setting("accent", accent) or accent
        for key, meta in ACCENTS.items():
            button = QToolButton()
            button.setCheckable(True)
            button.setAutoRaise(False)
            button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
            button.setText(meta.label)
            button.setIcon(icons.dot(meta.color, 18))
            button.setIconSize(QSize(18, 18))
            button.setFixedSize(68, 58)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setStyleSheet(
                "QToolButton {"
                "border: 2px solid #E5E9F2; border-radius: 10px;"
                "background: #F8FAFD; padding: 5px; font-size: 10px; font-weight: 600;"
                f"color: {MUTED};"
                "}"
                "QToolButton:hover { border-color: #C9D0DE; }"
                f"QToolButton:checked {{ border-color: {meta.color};"
                f"background: {meta.soft}; color: {meta.pressed}; }}"
            )
            button.setProperty("accent_key", key)
            self.accent_group.addButton(button)
            if key == current_accent:
                button.setChecked(True)
            accents.addWidget(button)
        accents.addStretch(1)
        appearance.addLayout(accents)

        # Reminders ----------------------------------------------------------
        reminders = self._section(
            "Reminders", "Stay on top of every plan without the noise."
        )
        self.notifications = QCheckBox("Show desktop notifications")
        self.notifications.setChecked(database.get_bool("notifications", True))
        reminders.addWidget(self.notifications)
        note = QLabel("In-app reminder cards are always shown while the app is open.")
        note.setStyleSheet(f"color: {FAINT}; font-size: 10px;")
        note.setWordWrap(True)
        reminders.addWidget(note)

        self.sound = QCheckBox("Play a soft sound with reminders")
        self.sound.setChecked(database.get_bool("sound", True))
        reminders.addWidget(self.sound)

        self.tray = QCheckBox("Keep running in the tray so reminders never miss")
        self.tray.setChecked(database.get_bool("close_to_tray", True))
        reminders.addWidget(self.tray)

        self.default_reminder = QComboBox()
        for minutes, label in REMINDER_CHOICES:
            if minutes is None:
                continue
            self.default_reminder.addItem(label, minutes)
        reminder_value = database.get_int("default_reminder", 15)
        self.default_reminder.setCurrentIndex(
            max(0, self.default_reminder.findData(reminder_value))
        )
        reminders.addWidget(
            self._row(
                "Default reminder",
                "Pre-selected when you create a new event.",
                self.default_reminder,
            )
        )

        # Data ---------------------------------------------------------------
        data = self._section(
            "Your data", "Everything stays in a local SQLite database on this device."
        )
        path = QLabel(str(app_data_dir()))
        path.setWordWrap(True)
        path.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        path.setStyleSheet(
            "background: #F8FAFD; border: 1px solid #E5E9F2; border-radius: 8px;"
            "padding: 9px 10px; color: #6C7488; font-size: 10px;"
        )
        data.addWidget(path)

        self.size_label = QLabel("")
        self.size_label.setStyleSheet(f"color: {FAINT}; font-size: 10px;")
        data.addWidget(self.size_label)

        data_buttons = QHBoxLayout()
        data_buttons.setSpacing(8)
        open_folder = QPushButton("Open folder")
        open_folder.setProperty("variant", "secondary")
        open_folder.setIcon(icons.icon("folder", MUTED, 15))
        open_folder.setCursor(Qt.CursorShape.PointingHandCursor)
        open_folder.clicked.connect(self._open_folder)
        data_buttons.addWidget(open_folder)
        backup = QPushButton("Back up database…")
        backup.setProperty("variant", "secondary")
        backup.setIcon(icons.icon("database", MUTED, 15))
        backup.setCursor(Qt.CursorShape.PointingHandCursor)
        backup.clicked.connect(self._backup)
        data_buttons.addWidget(backup)
        data_buttons.addStretch(1)
        data.addLayout(data_buttons)
        self._refresh_size()

        # About ---------------------------------------------------------------
        about = QFrame()
        about.setObjectName("SoftCard")
        about_layout = QHBoxLayout(about)
        about_layout.setContentsMargins(14, 12, 14, 12)
        about_layout.setSpacing(12)
        logo = QLabel()
        logo.setPixmap(icons.logo_pixmap(40))
        logo.setFixedSize(40, 40)
        about_layout.addWidget(logo)
        about_text = QVBoxLayout()
        about_text.setSpacing(1)
        name = QLabel(f"{APP_NAME}  ·  v{VERSION}")
        name.setStyleSheet(f"color: {INK}; font-size: 12px; font-weight: 700;")
        about_text.addWidget(name)
        tagline = QLabel("Local-first. Private by design. Beautifully simple.")
        tagline.setStyleSheet(f"color: {FAINT}; font-size: 10px;")
        about_text.addWidget(tagline)
        about_layout.addLayout(about_text, 1)
        content.addWidget(about)
        content.addStretch(1)

        root.addWidget(make_divider())
        footer = QHBoxLayout()
        footer.addStretch(1)
        cancel = QPushButton("Cancel")
        cancel.setProperty("variant", "secondary")
        cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel.clicked.connect(self.reject)
        footer.addWidget(cancel)
        save = QPushButton("Save settings")
        save.setProperty("variant", "primary")
        save.setCursor(Qt.CursorShape.PointingHandCursor)
        save.setDefault(True)
        save.clicked.connect(self._save)
        footer.addWidget(save)
        root.addLayout(footer)

    # ------------------------------------------------------------------ helpers
    def _section(self, title: str, subtitle: str) -> QVBoxLayout:
        frame = QFrame()
        frame.setObjectName("Card")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(16, 14, 16, 16)
        layout.setSpacing(9)
        heading = QLabel(title)
        heading.setStyleSheet(f"color: {INK}; font-size: 13px; font-weight: 700;")
        layout.addWidget(heading)
        detail = QLabel(subtitle)
        detail.setStyleSheet(f"color: {FAINT}; font-size: 10px;")
        detail.setWordWrap(True)
        layout.addWidget(detail)
        layout.addSpacing(2)
        self._content_layout.addWidget(frame)
        return layout

    def _row(self, title: str, hint: str, widget: QWidget) -> QWidget:
        wrapper = QWidget()
        layout = QHBoxLayout(wrapper)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        text = QVBoxLayout()
        text.setSpacing(1)
        label = QLabel(title)
        label.setObjectName("FieldLabel")
        text.addWidget(label)
        detail = QLabel(hint)
        detail.setStyleSheet(f"color: {FAINT}; font-size: 10px;")
        detail.setWordWrap(True)
        text.addWidget(detail)
        layout.addLayout(text, 1)
        layout.addWidget(widget, 0, Qt.AlignmentFlag.AlignVCenter)
        return wrapper

    def _save(self) -> None:
        checked = self.accent_group.checkedButton()
        accent_key = str(checked.property("accent_key")) if checked else self._accent
        settings = {
            "week_start": int(self.week_start.currentData()),
            "accent": accent_key,
            "notifications": self.notifications.isChecked(),
            "sound": self.sound.isChecked(),
            "close_to_tray": self.tray.isChecked(),
            "default_reminder": int(self.default_reminder.currentData()),
        }
        for key, value in settings.items():
            self.database.set_setting(key, value)
        self.settingsSaved.emit(settings)
        self.accept()

    def _open_folder(self) -> None:
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(app_data_dir())))

    def _backup(self) -> None:
        suggested = (
            Path.home()
            / f"book-my-date-backup-{datetime.now().strftime('%Y%m%d-%H%M')}.db"
        )
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Back up your calendar",
            str(suggested),
            "SQLite database (*.db);;All files (*)",
        )
        if not path:
            return
        try:
            target = self.database.backup(path)
        except OSError as exc:
            QMessageBox.critical(self, "Backup failed", str(exc))
            return
        QMessageBox.information(
            self,
            "Backup complete",
            f"Your calendar was backed up to:\n{target}",
        )
        self._refresh_size()

    def _refresh_size(self) -> None:
        path = Path(self.database.path)
        if path.exists():
            self.size_label.setText(
                f"Database size: {_human_size(path.stat().st_size)}"
            )
        else:
            self.size_label.setText("Database size: —")
