"""Main application window."""

from __future__ import annotations

from datetime import date

from PySide6.QtCore import QEvent, QPoint, QSettings, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QCloseEvent, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidget,
)

from ..config import APP_NAME, VERSION, asset_path
from ..core.calendar_utils import (
    group_events_by_day,
    long_date,
    month_grid,
    relative_day_label,
)
from ..core.database import Database, DatabaseError
from ..core.models import Event, TaskTopic
from ..core.notifications import notify as native_notify
from ..core.reminders import ReminderEngine
from . import icons
from .calendar_widget import CalendarWidget
from .day_panel import DayPanel
from .event_dialog import EventDialog
from .settings_dialog import SettingsDialog
from .task_dialog import TaskDialog
from .theme import MUTED, SIDEBAR_MUTED, accent_for, apply_theme
from .widgets import (
    ElidedLabel,
    Notice,
    SearchBox,
    SearchPopup,
    Toast,
    add_shadow,
)


class UpcomingItem(QFrame):
    activated = Signal(object)

    def __init__(self, event: Event, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._event = event
        self.setObjectName("SidebarCard")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(f"{event.title}\n{event.display_time_range()}")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(8)
        dot = QLabel()
        dot.setPixmap(icons.dot(event.category_meta.color, 8).pixmap(8, 8))
        dot.setFixedSize(8, 8)
        layout.addWidget(dot, 0, Qt.AlignmentFlag.AlignTop)

        text = QVBoxLayout()
        text.setSpacing(1)
        title = ElidedLabel(event.title)
        title.setStyleSheet(
            "color: #E9ECF6; font-size: 11px; font-weight: 600; background: transparent;"
        )
        text.addWidget(title)
        time_text = (
            "All day"
            if event.all_day
            else event.start_at.strftime("%H:%M")
        )
        meta = QLabel(f"{relative_day_label(event.start_at.date())} · {time_text}")
        meta.setStyleSheet(
            f"color: {SIDEBAR_MUTED}; font-size: 9px; background: transparent;"
        )
        text.addWidget(meta)
        layout.addLayout(text, 1)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self.activated.emit(self._event)
        super().mouseReleaseEvent(event)


class MainWindow(QMainWindow):
    def __init__(
        self,
        database: Database,
        engine: ReminderEngine,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.database = database
        self.engine = engine
        self._closed_to_tray = False
        self._really_quit = False
        self._active_toasts: list[Toast] = []
        self._tray_hint_shown = False
        self._today = date.today()

        self.accent_key = database.get_setting("accent", "indigo") or "indigo"
        self.week_start = database.get_int("week_start", 0)
        self.notifications_enabled = database.get_bool("notifications", True)
        self.sound_enabled = database.get_bool("sound", True)
        self.close_to_tray = database.get_bool("close_to_tray", True)

        self.setWindowTitle(f"{APP_NAME} — Calendar")
        self.setWindowIcon(icons.app_icon())
        self.setMinimumSize(1120, 760)
        self.resize(1380, 900)

        self._build_ui()
        self._build_shortcuts()
        self._setup_tray()
        self._restore_geometry()

        self.calendar.dateSelected.connect(self._on_date_selected)
        self.calendar.eventActivated.connect(self._edit_event)
        self.calendar.topicActivated.connect(self._edit_topic)
        self.calendar.addRequested.connect(self._new_event)
        self.calendar.monthChanged.connect(self._on_month_changed)

        self.day_panel.addRequested.connect(self._new_event)
        self.day_panel.taskRequested.connect(self._new_topic)
        self.day_panel.editRequested.connect(self._edit_event)
        self.day_panel.taskEditRequested.connect(self._edit_topic)
        self.day_panel.deleteRequested.connect(self._delete_event)
        self.day_panel.progressChanged.connect(self._set_progress)
        self.day_panel.percentChanged.connect(self._set_topic_progress)
        self.day_panel.percentReset.connect(self._reset_topic_progress)
        self.search.textChanged.connect(self._on_search)
        self.search.returnPressed.connect(self._open_first_result)
        self.search_popup.eventChosen.connect(self._on_search_choice)

        self.calendar.set_month(
            date.today().year,
            date.today().month,
            select_day=date.today(),
            emit=False,
        )
        self._refresh_all()
        app = QApplication.instance()
        if app is not None:
            app.installEventFilter(self)

        self.reminder_timer = QTimer(self)
        self.reminder_timer.setInterval(20000)
        self.reminder_timer.timeout.connect(self._check_reminders)
        self.reminder_timer.start()
        QTimer.singleShot(1400, self._check_reminders)

    # ------------------------------------------------------------------- build
    def _build_ui(self) -> None:
        root = QWidget()
        root.setObjectName("Root")
        self.setCentralWidget(root)
        layout = QHBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        layout.addWidget(self._build_sidebar())

        main = QWidget()
        main.setObjectName("Root")
        main_layout = QVBoxLayout(main)
        main_layout.setContentsMargins(22, 18, 22, 18)
        main_layout.setSpacing(14)
        main_layout.addLayout(self._build_topbar())

        content = QHBoxLayout()
        content.setSpacing(14)
        self.calendar = CalendarWidget(
            week_start=self.week_start, accent=self.accent_key
        )
        add_shadow(self.calendar, blur=34, y_offset=9, alpha=22)
        content.addWidget(self.calendar, 1)

        self.day_panel = DayPanel(accent=self.accent_key)
        add_shadow(self.day_panel, blur=34, y_offset=9, alpha=22)
        content.addWidget(self.day_panel, 0)
        main_layout.addLayout(content, 1)
        layout.addWidget(main, 1)

        self.search_popup = SearchPopup(self)
        self.notice = Notice(self)
        self._refresh_header(date.today())

    def _build_topbar(self) -> QHBoxLayout:
        bar = QHBoxLayout()
        bar.setSpacing(12)
        titles = QVBoxLayout()
        titles.setSpacing(0)
        self.header_kicker = QLabel("")
        self.header_kicker.setStyleSheet(
            f"color: {accent_for(self.accent_key).color}; font-size: 9px; font-weight: 800;"
        )
        titles.addWidget(self.header_kicker)
        title = QLabel("Your calendar")
        title.setObjectName("PageTitle")
        titles.addWidget(title)
        subtitle = QLabel("A calm home for every plan, reminder and moment.")
        subtitle.setStyleSheet(f"color: {MUTED}; font-size: 11px;")
        titles.addWidget(subtitle)
        bar.addLayout(titles)
        bar.addStretch(1)

        self.search = SearchBox()
        self.search.setFixedWidth(290)
        bar.addWidget(self.search, 0, Qt.AlignmentFlag.AlignVCenter)

        self.new_button = QPushButton("New event")
        self.new_button.setProperty("variant", "primary")
        self.new_button.setIcon(icons.icon("plus", "#FFFFFF", 16))
        self.new_button.setIconSize(QSize(15, 15))
        self.new_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.new_button.setFixedHeight(40)
        self.new_button.clicked.connect(lambda: self._new_event(self.calendar.selected_date))
        bar.addWidget(self.new_button, 0, Qt.AlignmentFlag.AlignVCenter)

        self.new_task_button = QPushButton("New task")
        self.new_task_button.setProperty("variant", "secondary")
        self.new_task_button.setIcon(icons.icon("check-circle", accent_for(self.accent_key).color, 16))
        self.new_task_button.setIconSize(QSize(15, 15))
        self.new_task_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.new_task_button.setFixedHeight(40)
        self.new_task_button.clicked.connect(lambda: self._new_topic(self.calendar.selected_date))
        bar.addWidget(self.new_task_button, 0, Qt.AlignmentFlag.AlignVCenter)
        return bar

    def _build_sidebar(self) -> QFrame:
        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(258)
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(18, 20, 18, 16)
        layout.setSpacing(12)

        brand = QHBoxLayout()
        brand.setSpacing(10)
        logo = QLabel()
        logo.setPixmap(icons.logo_pixmap(42))
        logo.setFixedSize(42, 42)
        brand.addWidget(logo)
        brand_text = QVBoxLayout()
        brand_text.setSpacing(0)
        name = QLabel(APP_NAME)
        name.setStyleSheet(
            "color: #FFFFFF; font-size: 15px; font-weight: 800; background: transparent;"
        )
        brand_text.addWidget(name)
        tagline = QLabel("Private, local-first planner")
        tagline.setObjectName("SidebarMuted")
        tagline.setStyleSheet(
            f"color: {SIDEBAR_MUTED}; font-size: 9px; background: transparent;"
        )
        brand_text.addWidget(tagline)
        brand.addLayout(brand_text, 1)
        layout.addLayout(brand)

        self.sidebar_new = QPushButton("  New event")
        self.sidebar_new.setProperty("variant", "primary")
        self.sidebar_new.setIcon(icons.icon("plus", "#FFFFFF", 17))
        self.sidebar_new.setIconSize(QSize(16, 16))
        self.sidebar_new.setCursor(Qt.CursorShape.PointingHandCursor)
        self.sidebar_new.setFixedHeight(42)
        self.sidebar_new.clicked.connect(lambda: self._new_event(self.calendar.selected_date))
        layout.addWidget(self.sidebar_new)

        self.sidebar_task = QPushButton("  New task topic")
        self.sidebar_task.setProperty("variant", "sidebar")
        self.sidebar_task.setIcon(icons.icon("check-circle", SIDEBAR_MUTED, 16))
        self.sidebar_task.setIconSize(QSize(15, 15))
        self.sidebar_task.setCursor(Qt.CursorShape.PointingHandCursor)
        self.sidebar_task.setFixedHeight(38)
        self.sidebar_task.clicked.connect(lambda: self._new_topic(self.calendar.selected_date))
        layout.addWidget(self.sidebar_task)

        divider = QFrame()
        divider.setObjectName("SidebarDivider")
        divider.setFixedHeight(1)
        layout.addWidget(divider)

        upcoming_label = QLabel("UPCOMING")
        upcoming_label.setObjectName("SidebarSection")
        upcoming_label.setStyleSheet(
            f"color: {SIDEBAR_MUTED}; font-size: 9px; font-weight: 800;"
            "background: transparent;"
        )
        layout.addWidget(upcoming_label)

        self.upcoming_host = QWidget()
        self.upcoming_host.setStyleSheet("background: transparent;")
        self.upcoming_layout = QVBoxLayout(self.upcoming_host)
        self.upcoming_layout.setContentsMargins(0, 0, 0, 0)
        self.upcoming_layout.setSpacing(6)
        layout.addWidget(self.upcoming_host)

        layout.addStretch(1)

        stats_label = QLabel("THIS MONTH")
        stats_label.setObjectName("SidebarSection")
        stats_label.setStyleSheet(
            f"color: {SIDEBAR_MUTED}; font-size: 9px; font-weight: 800;"
            "background: transparent;"
        )
        layout.addWidget(stats_label)

        stats = QFrame()
        stats.setObjectName("SidebarCard")
        stats_layout = QVBoxLayout(stats)
        stats_layout.setContentsMargins(12, 10, 12, 10)
        stats_layout.setSpacing(6)
        self.stat_events = self._stat_row(stats_layout, "Events")
        self.stat_reminders = self._stat_row(stats_layout, "Reminders")
        self.stat_today = self._stat_row(stats_layout, "Today")
        layout.addWidget(stats)

        bottom = QPushButton("  Settings")
        bottom.setProperty("variant", "sidebar")
        bottom.setIcon(icons.icon("settings", SIDEBAR_MUTED, 16))
        bottom.setIconSize(QSize(15, 15))
        bottom.setCursor(Qt.CursorShape.PointingHandCursor)
        bottom.setFixedHeight(38)
        bottom.clicked.connect(self._open_settings)
        layout.addWidget(bottom)

        version = QLabel(f"v{VERSION}")
        version.setAlignment(Qt.AlignmentFlag.AlignCenter)
        version.setStyleSheet(
            "color: #5F6A85; font-size: 9px; background: transparent;"
        )
        layout.addWidget(version)
        return sidebar

    @staticmethod
    def _stat_row(layout: QVBoxLayout, label_text: str) -> QLabel:
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        label = QLabel(label_text)
        label.setStyleSheet(
            f"color: {SIDEBAR_MUTED}; font-size: 10px; background: transparent;"
        )
        row.addWidget(label)
        row.addStretch(1)
        value = QLabel("0")
        value.setStyleSheet(
            "color: #FFFFFF; font-size: 12px; font-weight: 700; background: transparent;"
        )
        row.addWidget(value)
        layout.addLayout(row)
        return value

    def _build_shortcuts(self) -> None:
        self._shortcuts: list[QShortcut] = []
        for sequence, callback in (
            ("Ctrl+N", lambda: self._new_event(self.calendar.selected_date)),
            ("Ctrl+Shift+T", lambda: self._new_topic(self.calendar.selected_date)),
            ("Ctrl+F", self._focus_search),
            ("Ctrl+,", self._open_settings),
            ("Ctrl+Left", lambda: self.calendar.prev_button.click()),
            ("Ctrl+Right", lambda: self.calendar.next_button.click()),
            ("Ctrl+T", lambda: self.calendar.go_today()),
            ("Escape", self._escape),
        ):
            shortcut = QShortcut(QKeySequence(sequence), self)
            shortcut.activated.connect(callback)
            self._shortcuts.append(shortcut)

    def _restore_geometry(self) -> None:
        settings = QSettings("BookMyDate", "BookMyDate")
        geometry = settings.value("window/geometry")
        if geometry:
            self.restoreGeometry(geometry)

    # ------------------------------------------------------------------- tray
    def _setup_tray(self) -> None:
        self.tray: QSystemTrayIcon | None = None
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return
        icon = icons.app_icon()
        if icon.isNull():
            return
        self.tray = QSystemTrayIcon(icon, self)
        self.tray.setToolTip(APP_NAME)
        menu = QMenu()
        open_action = menu.addAction("Open Book My Date")
        open_action.triggered.connect(self._show_window)
        new_action = menu.addAction("New event")
        new_action.triggered.connect(self._tray_new_event)
        new_task_action = menu.addAction("New task topic")
        new_task_action.triggered.connect(self._tray_new_topic)
        menu.addSeparator()
        quit_action = menu.addAction("Quit")
        quit_action.triggered.connect(self.quit_app)
        self._tray_menu = menu
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self._on_tray_activated)
        self.tray.show()
        self._update_tray_tooltip()

    def _on_tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason in (
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        ):
            self._show_window()

    def _show_window(self) -> None:
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def show_window(self) -> None:
        self._show_window()

    def _tray_new_event(self) -> None:
        self._show_window()
        self._new_event(self.calendar.selected_date)

    def _tray_new_topic(self) -> None:
        self._show_window()
        self._new_topic(self.calendar.selected_date)

    def _update_tray_tooltip(self) -> None:
        if self.tray is None:
            return
        upcoming = self.database.upcoming_events(1)
        if not upcoming:
            self.tray.setToolTip(f"{APP_NAME}\nNo upcoming events")
            return
        event = upcoming[0]
        when = relative_day_label(event.start_at.date())
        clock = "All day" if event.all_day else event.start_at.strftime("%H:%M")
        self.tray.setToolTip(f"{APP_NAME}\nNext: {event.title}\n{when} · {clock}")

    # ----------------------------------------------------------------- refresh
    def _refresh_all(self) -> None:
        self._refresh_calendar_data()
        self._refresh_sidebar()
        self._refresh_header(self.calendar.selected_date)
        self._on_date_selected(self.calendar.selected_date)
        self._update_tray_tooltip()

    def _refresh_calendar_data(self) -> None:
        grid = month_grid(
            self.calendar.year, self.calendar.month, self.week_start
        )
        start, end = grid[0][0], grid[-1][-1]
        events = self.database.list_events(start, end)
        self.calendar.set_events(group_events_by_day(events))
        self.calendar.set_topics(self.database.topics_by_day(start, end))

    def _refresh_sidebar(self) -> None:
        while self.upcoming_layout.count():
            item = self.upcoming_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        upcoming = self.database.upcoming_events(4)
        if not upcoming:
            empty = QLabel("No upcoming events.\nEnjoy the calm.")
            empty.setStyleSheet(
                f"color: {SIDEBAR_MUTED}; font-size: 10px; background: transparent;"
                "padding: 8px 2px;"
            )
            self.upcoming_layout.addWidget(empty)
        else:
            for event in upcoming:
                item = UpcomingItem(event)
                item.activated.connect(self._on_upcoming_activated)
                self.upcoming_layout.addWidget(item)

        stats = self.database.statistics()
        self.stat_events.setText(str(stats["this_month"]))
        self.stat_reminders.setText(str(stats["reminders"]))
        self.stat_today.setText(str(stats["today"]))

    def _refresh_header(self, day: date) -> None:
        prefix = "TODAY · " if day == date.today() else ""
        self.header_kicker.setText(f"{prefix}{long_date(day).upper()}")
        self.header_kicker.setStyleSheet(
            f"color: {accent_for(self.accent_key).color}; font-size: 9px; "
            "font-weight: 800;"
        )

    # ------------------------------------------------------------------ events
    def _on_date_selected(self, day: date) -> None:
        self.search_popup.hide()
        self._refresh_header(day)
        events = self.database.events_for_day(day)
        topics = self.database.topics_for_day(day)
        self.day_panel.set_day(day, events, topics)

    def _on_month_changed(self, _year: int, _month: int) -> None:
        self._refresh_calendar_data()
        self._refresh_header(self.calendar.selected_date)

    def _on_upcoming_activated(self, event: Event) -> None:
        self.calendar.show_date(event.start_at.date())
        self._show_window()

    def _new_event(self, selected_date: date) -> None:
        dialog = EventDialog(
            selected_date=selected_date,
            accent=self.accent_key,
            default_reminder=self.database.get_int("default_reminder", 15),
            parent=self,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        if dialog.deleted or dialog.created_event() is None:
            return
        try:
            saved = self.database.add_event(dialog.created_event())
        except (DatabaseError, ValueError) as exc:
            QMessageBox.critical(self, "Could not save event", str(exc))
            return
        self._after_mutation(saved)
        self._show_notice("Event created and saved to your calendar.")

    def _edit_event(self, event: Event) -> None:
        fresh = self.database.get_event(event.id) if event.id is not None else event
        if fresh is None:
            self._show_notice("That event no longer exists.", kind="error")
            self._refresh_all()
            return
        dialog = EventDialog(
            selected_date=fresh.start_at.date(),
            accent=self.accent_key,
            default_reminder=self.database.get_int("default_reminder", 15),
            event=fresh,
            parent=self,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        if dialog.deleted:
            self._perform_delete(fresh)
            return
        updated = dialog.created_event()
        if updated is None:
            return
        try:
            saved = self.database.update_event(updated)
        except (DatabaseError, ValueError) as exc:
            QMessageBox.critical(self, "Could not update event", str(exc))
            return
        self._after_mutation(saved)
        self._show_notice("Event updated.")

    def _delete_event(self, event: Event) -> None:
        answer = QMessageBox.question(
            self,
            "Delete event?",
            f"“{event.title}” will be permanently deleted.",
            QMessageBox.StandardButton.Delete | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if answer == QMessageBox.StandardButton.Delete:
            self._perform_delete(event)

    def _perform_delete(self, event: Event) -> None:
        if event.id is None or not self.database.delete_event(event.id):
            self._show_notice("That event no longer exists.", kind="error")
        else:
            self._show_notice("Event deleted.")
        self._refresh_all()

    def _after_mutation(self, event: Event) -> None:
        target = event.start_at.date()
        if (target.year, target.month) != (
            self.calendar.year,
            self.calendar.month,
        ):
            self.calendar.show_date(target, emit=False)
        self.calendar.set_selected(target, emit=False)
        self._refresh_all()
        QTimer.singleShot(600, self._check_reminders)

    # ------------------------------------------------------------ task topics
    def _new_topic(self, selected_date: date) -> None:
        dialog = TaskDialog(
            selected_date=selected_date,
            accent=self.accent_key,
            parent=self,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        topic = dialog.created_topic()
        if topic is None:
            return
        try:
            self.database.add_topic(topic)
        except (DatabaseError, ValueError) as exc:
            QMessageBox.critical(self, "Could not save task topic", str(exc))
            return
        self._refresh_all()
        self._show_notice("Task topic created. It appears on your calendar dates.")

    def _edit_topic(self, topic: TaskTopic) -> None:
        fresh = self.database.get_topic(topic.id) if topic.id is not None else topic
        if fresh is None:
            self._show_notice("That task topic no longer exists.", kind="error")
            self._refresh_all()
            return
        dialog = TaskDialog(
            selected_date=self.calendar.selected_date,
            accent=self.accent_key,
            topic=fresh,
            parent=self,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        if dialog.deleted:
            if topic.id is None or not self.database.delete_topic(topic.id):
                self._show_notice("That task topic no longer exists.", kind="error")
            else:
                self._show_notice("Task topic deleted.")
            self._refresh_all()
            return
        updated = dialog.created_topic()
        if updated is None:
            return
        try:
            self.database.update_topic(updated)
        except (DatabaseError, ValueError) as exc:
            QMessageBox.critical(self, "Could not update task topic", str(exc))
            return
        self._refresh_all()
        self._show_notice("Task topic updated.")

    def _set_progress(self, topic_id: int, subtask_id: int, status: int) -> None:
        try:
            self.database.set_subtask_progress(
                subtask_id, self.calendar.selected_date, status
            )
        except (DatabaseError, ValueError) as exc:
            self._show_notice(f"Could not save progress: {exc}", kind="error")
            return
        self._defer_progress_refresh()

    def _set_topic_progress(self, topic_id: int, percent: int) -> None:
        try:
            self.database.set_topic_progress(
                topic_id, self.calendar.selected_date, percent
            )
        except (DatabaseError, ValueError) as exc:
            self._show_notice(f"Could not save completion: {exc}", kind="error")
            return
        self._defer_progress_refresh()

    def _reset_topic_progress(self, topic_id: int) -> None:
        try:
            self.database.clear_topic_progress(topic_id, self.calendar.selected_date)
        except DatabaseError as exc:
            self._show_notice(f"Could not reset completion: {exc}", kind="error")
            return
        self._defer_progress_refresh()

    def _defer_progress_refresh(self) -> None:
        QTimer.singleShot(0, self._apply_progress_refresh)

    def _apply_progress_refresh(self) -> None:
        self._refresh_calendar_data()
        self._on_date_selected(self.calendar.selected_date)

    # ------------------------------------------------------------------ search
    def _on_search(self, text: str) -> None:
        query = text.strip()
        if not query:
            self.search_popup.hide()
            return
        results = self.database.search_events(query, limit=7)
        self.search_popup.show_results(results, query)
        position = self.search.mapToGlobal(QPoint(0, self.search.height() + 8))
        screen = self.screen()
        if screen is not None:
            available = screen.availableGeometry()
            if position.x() + self.search_popup.width() > available.right() - 12:
                position.setX(available.right() - self.search_popup.width() - 12)
            if position.y() + self.search_popup.height() > available.bottom() - 12:
                position.setY(
                    self.search.mapToGlobal(QPoint(0, 0)).y()
                    - self.search_popup.height()
                    - 8
                )
        self.search_popup.move(position)
        self.search_popup.raise_()

    def _open_first_result(self) -> None:
        query = self.search.text().strip()
        if not query:
            return
        results = self.database.search_events(query, limit=1)
        if results:
            self._on_search_choice(results[0])

    def _on_search_choice(self, event: Event) -> None:
        self.search.blockSignals(True)
        self.search.clear()
        self.search.blockSignals(False)
        self.search_popup.hide()
        self.calendar.show_date(event.start_at.date())
        QTimer.singleShot(80, lambda: self._edit_event(event))

    def _focus_search(self) -> None:
        self.search.setFocus()
        self.search.selectAll()

    def _escape(self) -> None:
        if self.search_popup.isVisible():
            self.search_popup.hide()
        if self.search.text():
            self.search.clear()

    # --------------------------------------------------------------- reminders
    def _check_reminders(self) -> None:
        today = date.today()
        if today != self._today:
            self._today = today
            self.calendar.refresh_today()
            self._refresh_all()
        events = self.engine.pop_due()
        for event in events:
            self._show_reminder(event)
        self._update_tray_tooltip()

    def _show_reminder(self, event: Event) -> None:
        toast = Toast(event, self)
        toast.snoozed.connect(self._snooze_reminder)
        toast.opened.connect(lambda item: self._open_event_by_id(item.id))
        toast.dismissed.connect(lambda _item: self._forget_toast(toast))
        bottom_right = self.mapToGlobal(
            QPoint(self.width() - 18, self.height() - 18)
        )
        toast.present(bottom_right, len(self._active_toasts))
        self._active_toasts.append(toast)

        if self.sound_enabled:
            QApplication.beep()

        if self.notifications_enabled:
            body = f"{event.title}\n{event.notification_body()}"
            if self.tray is not None and self.tray.isVisible():
                self.tray.showMessage(
                    APP_NAME,
                    body,
                    QSystemTrayIcon.MessageIcon.Information,
                    9000,
                )
            else:
                native_notify(
                    APP_NAME,
                    body,
                    icon=asset_path("app_icon_256.png"),
                )

    def _forget_toast(self, toast: Toast) -> None:
        if toast in self._active_toasts:
            self._active_toasts.remove(toast)

    def _snooze_reminder(self, event: Event) -> None:
        self.engine.snooze(event, minutes=10)
        self._show_notice("Reminder snoozed for 10 minutes.")

    def _open_event_by_id(self, event_id: int | None) -> None:
        if event_id is None:
            return
        event = self.database.get_event(event_id)
        if event is None:
            self._show_notice("That event no longer exists.", kind="error")
            return
        self.calendar.show_date(event.start_at.date())
        self._show_window()
        QTimer.singleShot(80, lambda: self._edit_event(event))

    # ---------------------------------------------------------------- settings
    def _open_settings(self) -> None:
        dialog = SettingsDialog(self.database, accent=self.accent_key, parent=self)
        dialog.settingsSaved.connect(self._apply_settings)
        dialog.exec()

    def _apply_settings(self, settings: dict) -> None:
        self.accent_key = str(settings.get("accent", self.accent_key))
        self.week_start = int(settings.get("week_start", self.week_start))
        self.notifications_enabled = bool(
            settings.get("notifications", self.notifications_enabled)
        )
        self.sound_enabled = bool(settings.get("sound", self.sound_enabled))
        self.close_to_tray = bool(
            settings.get("close_to_tray", self.close_to_tray)
        )
        app = QApplication.instance()
        if app is not None:
            apply_theme(app, self.accent_key)
        self.calendar.set_accent(self.accent_key)
        self.calendar.set_week_start(self.week_start)
        self.day_panel.set_accent(self.accent_key)
        self.new_task_button.setIcon(
            icons.icon("check-circle", accent_for(self.accent_key).color, 16)
        )
        self._refresh_all()
        self._show_notice("Settings saved.")

    def _show_notice(self, message: str, *, kind: str = "success") -> None:
        anchor = self.mapToGlobal(QPoint(self.width() // 2, self.height() - 28))
        self.notice.show_message(message, kind=kind, anchor=anchor)

    # ------------------------------------------------------------------ window
    def eventFilter(self, watched, event) -> bool:  # noqa: N802
        if (
            event.type() == QEvent.Type.MouseButtonPress
            and hasattr(self, "search_popup")
            and self.search_popup.isVisible()
        ):
            widget = QApplication.widgetAt(event.globalPosition().toPoint())
            inside = widget is not None and (
                widget is self.search_popup
                or self.search_popup.isAncestorOf(widget)
                or widget is self.search
                or self.search.isAncestorOf(widget)
            )
            if not inside:
                self.search_popup.hide()
        return super().eventFilter(watched, event)

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        if hasattr(self, "search_popup"):
            self.search_popup.hide()

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        self._save_geometry()
        if (
            not self._really_quit
            and self.close_to_tray
            and self.tray is not None
            and self.tray.isVisible()
        ):
            event.ignore()
            self.hide()
            self._closed_to_tray = True
            if not self._tray_hint_shown:
                self._tray_hint_shown = True
                self.tray.showMessage(
                    APP_NAME,
                    "Still running in the tray so reminders reach you.",
                    QSystemTrayIcon.MessageIcon.Information,
                    5000,
                )
            return
        event.accept()

    def _save_geometry(self) -> None:
        settings = QSettings("BookMyDate", "BookMyDate")
        settings.setValue("window/geometry", self.saveGeometry())

    def quit_app(self) -> None:
        self._really_quit = True
        self._save_geometry()
        if self.tray is not None:
            self.tray.hide()
        QApplication.quit()
