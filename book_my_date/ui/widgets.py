"""Reusable, themed UI components."""

from __future__ import annotations

from datetime import date
from typing import Iterable

from PySide6.QtCore import QEvent, QPoint, QPropertyAnimation, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFontMetrics, QGuiApplication
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ..core.calendar_utils import short_date
from ..core.models import Event, category_for, reminder_label
from . import icons
from .theme import FAINT, INK, MUTED


def add_shadow(
    widget: QWidget,
    *,
    blur: int = 28,
    y_offset: int = 8,
    color: str = "#1B2440",
    alpha: int = 28,
) -> None:
    shadow = QGraphicsDropShadowEffect(widget)
    shadow.setBlurRadius(blur)
    shadow.setOffset(0, y_offset)
    rgb = QColor(color)
    shadow.setColor(
        QColor(rgb.red(), rgb.green(), rgb.blue(), max(0, min(255, alpha)))
    )
    widget.setGraphicsEffect(shadow)


def make_divider() -> QFrame:
    line = QFrame()
    line.setObjectName("Divider")
    line.setFrameShape(QFrame.Shape.NoFrame)
    line.setFixedHeight(1)
    return line


class Card(QFrame):
    def __init__(self, parent: QWidget | None = None, *, shadow: bool = False) -> None:
        super().__init__(parent)
        self.setObjectName("Card")
        if shadow:
            add_shadow(self)


class ElidedLabel(QLabel):
    """A label that gracefully truncates text instead of stretching layouts."""

    def __init__(self, text: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._full_text = ""
        self._updating = False
        self.setText(text)

    def setText(self, text: str) -> None:  # noqa: N802 - Qt naming
        self._full_text = text or ""
        self._update_elided()

    def full_text(self) -> str:
        return self._full_text

    def resizeEvent(self, event: QEvent) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._update_elided()

    def _update_elided(self) -> None:
        if self._updating:
            return
        self._updating = True
        try:
            width = max(0, self.contentsRect().width())
            text = QFontMetrics(self.font()).elidedText(
                self._full_text, Qt.TextElideMode.ElideRight, width
            )
            super().setText(text)
            self.setToolTip(self._full_text if text != self._full_text else "")
        finally:
            self._updating = False


class SectionLabel(QLabel):
    def __init__(self, text: str = "", parent: QWidget | None = None) -> None:
        super().__init__(text.upper(), parent)
        self.setObjectName("SectionLabel")


class IconButton(QPushButton):
    def __init__(
        self,
        icon_name: str,
        *,
        size: int = 34,
        icon_size: int = 18,
        color: str = MUTED,
        tooltip: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("IconButton")
        self.setFixedSize(size, size)
        self.setIconSize(QSize(icon_size, icon_size))
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._icon_name = icon_name
        self._icon_size = icon_size
        self._color = color
        self.set_icon(icon_name, color)
        if tooltip:
            self.setToolTip(tooltip)

    def set_icon(self, name: str, color: str = MUTED) -> None:
        self._icon_name = name
        self._color = color
        self.setIcon(icons.icon(name, color, self._icon_size))

    def enterEvent(self, event: QEvent) -> None:  # noqa: N802
        self.set_icon(self._icon_name, INK)
        super().enterEvent(event)

    def leaveEvent(self, event: QEvent) -> None:  # noqa: N802
        self.set_icon(self._icon_name, self._color)
        super().leaveEvent(event)


class SearchBox(QLineEdit):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("SearchBox")
        self.setPlaceholderText("Search events, places, notes…")
        self.setClearButtonEnabled(True)
        self.addAction(icons.icon("search", FAINT, 17), QLineEdit.ActionPosition.LeadingPosition)
        self.setMinimumHeight(40)


class CategoryBadge(QLabel):
    def __init__(self, category: str, parent: QWidget | None = None) -> None:
        meta = category_for(category)
        super().__init__(meta.label, parent)
        self.setStyleSheet(
            "QLabel {"
            f"color: {meta.text_color}; background: {meta.soft_color};"
            "border-radius: 6px; padding: 2px 7px; font-size: 10px; font-weight: 700;"
            "}"
        )
        self.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)


class EventChip(QFrame):
    clicked = Signal(object)

    def __init__(
        self,
        event: Event,
        day: date,
        *,
        continuation: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        meta = event.category_meta
        self._event = event
        self.setObjectName("EventChip")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(21)
        self.setStyleSheet(
            "QFrame#EventChip {"
            f"background: {meta.soft_color}; border-radius: 5px; border: none;"
            "}"
            "QFrame#EventChip:hover {"
            f"background: {meta.soft_color}; border: 1px solid {meta.color};"
            "}"
        )
        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 1, 6, 1)
        layout.setSpacing(4)

        dot = QLabel()
        dot.setPixmap(icons.dot(meta.color, 7).pixmap(7, 7))
        dot.setFixedSize(7, 7)
        layout.addWidget(dot, 0, Qt.AlignmentFlag.AlignVCenter)

        if event.all_day:
            time_text = "All day"
        elif continuation or event.start_at.date() != day:
            time_text = "→"
        else:
            time_text = event.start_at.strftime("%H:%M")
        time_label = QLabel(time_text)
        time_label.setStyleSheet(
            f"color: {meta.text_color}; font-size: 9px; font-weight: 700; background: transparent;"
        )
        time_label.setFixedWidth(38 if time_text != "→" else 12)
        layout.addWidget(time_label, 0, Qt.AlignmentFlag.AlignVCenter)

        title = ElidedLabel(event.title)
        title.setStyleSheet(
            f"color: {meta.text_color}; font-size: 10px; font-weight: 600; background: transparent;"
        )
        layout.addWidget(title, 1, Qt.AlignmentFlag.AlignVCenter)

    def mouseReleaseEvent(self, event: QEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self._event)
        super().mouseReleaseEvent(event)


class EventCard(QFrame):
    editRequested = Signal(object)
    deleteRequested = Signal(object)

    def __init__(self, event: Event, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._event = event
        self.setObjectName("EventCard")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 12, 12)
        layout.setSpacing(6)

        top = QHBoxLayout()
        top.setSpacing(8)
        top.addWidget(CategoryBadge(event.category))
        time = QLabel(event.display_time_range())
        time.setObjectName("Muted")
        time.setStyleSheet(f"color: {MUTED}; font-size: 11px; font-weight: 600;")
        top.addWidget(time)
        top.addStretch(1)

        edit = IconButton("edit", size=27, icon_size=14, tooltip="Edit event")
        edit.clicked.connect(lambda: self.editRequested.emit(self._event))
        delete = IconButton("trash", size=27, icon_size=14, tooltip="Delete event")
        delete.clicked.connect(lambda: self.deleteRequested.emit(self._event))
        top.addWidget(edit)
        top.addWidget(delete)
        layout.addLayout(top)

        title = QLabel(event.title)
        title.setWordWrap(True)
        title.setStyleSheet("font-size: 14px; font-weight: 700; color: #161D2F;")
        layout.addWidget(title)

        if event.location:
            location = QHBoxLayout()
            location.setSpacing(5)
            pin = QLabel()
            pin.setPixmap(icons.icon("map-pin", FAINT, 13).pixmap(13, 13))
            pin.setFixedSize(13, 13)
            location.addWidget(pin)
            location_text = ElidedLabel(event.location)
            location_text.setStyleSheet(f"color: {MUTED}; font-size: 11px;")
            location.addWidget(location_text, 1)
            layout.addLayout(location)

        if event.description:
            description = QLabel(event.short_description(180))
            description.setWordWrap(True)
            description.setStyleSheet(f"color: {MUTED}; font-size: 11px; line-height: 1.4;")
            layout.addWidget(description)

        footer = QHBoxLayout()
        footer.setSpacing(5)
        if event.reminder_minutes is not None:
            bell = QLabel()
            bell.setPixmap(icons.icon("bell", FAINT, 12).pixmap(12, 12))
            bell.setFixedSize(12, 12)
            footer.addWidget(bell)
            reminder = QLabel(reminder_label(event.reminder_minutes))
            reminder.setStyleSheet(f"color: {FAINT}; font-size: 10px;")
            footer.addWidget(reminder)
        footer.addStretch(1)
        if event.is_past():
            status = QLabel("Past")
            status.setStyleSheet(
                "color: #8A93A6; background: #F1F3F8; border-radius: 5px;"
                "padding: 1px 6px; font-size: 9px; font-weight: 700;"
            )
            footer.addWidget(status)
        layout.addLayout(footer)

    def mouseReleaseEvent(self, event: QEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self.editRequested.emit(self._event)
        super().mouseReleaseEvent(event)

    def contextMenuEvent(self, event: QEvent) -> None:  # noqa: N802
        from PySide6.QtWidgets import QMenu

        menu = QMenu(self)
        edit = menu.addAction(icons.icon("edit", MUTED, 16), "Edit event")
        delete = menu.addAction(icons.icon("trash", "#DC2626", 16), "Delete event")
        chosen = menu.exec(event.globalPos())
        if chosen == edit:
            self.editRequested.emit(self._event)
        elif chosen == delete:
            self.deleteRequested.emit(self._event)


class EmptyState(QWidget):
    def __init__(
        self,
        icon_name: str,
        title: str,
        subtitle: str = "",
        *,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 24, 16, 24)
        layout.setSpacing(8)
        layout.addStretch(1)

        circle = QLabel()
        circle.setFixedSize(58, 58)
        circle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        circle.setPixmap(icons.icon(icon_name, FAINT, 26).pixmap(26, 26))
        circle.setStyleSheet(
            "background: #F3F5FA; border: 1px solid #E8EBF3; border-radius: 29px;"
        )
        layout.addWidget(circle, 0, Qt.AlignmentFlag.AlignHCenter)

        heading = QLabel(title)
        heading.setAlignment(Qt.AlignmentFlag.AlignCenter)
        heading.setStyleSheet(f"color: {INK}; font-size: 13px; font-weight: 700;")
        layout.addWidget(heading)

        if subtitle:
            text = QLabel(subtitle)
            text.setAlignment(Qt.AlignmentFlag.AlignCenter)
            text.setWordWrap(True)
            text.setStyleSheet(f"color: {FAINT}; font-size: 11px;")
            layout.addWidget(text)

        layout.addStretch(1)


class SearchRow(QFrame):
    clicked = Signal(object)

    def __init__(self, event: Event, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._event = event
        self.setObjectName("SearchRow")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 7, 10, 7)
        layout.setSpacing(10)
        meta = event.category_meta

        dot = QLabel()
        dot.setPixmap(icons.dot(meta.color, 8).pixmap(8, 8))
        dot.setFixedSize(8, 8)
        layout.addWidget(dot, 0, Qt.AlignmentFlag.AlignTop)

        text = QVBoxLayout()
        text.setSpacing(1)
        title = ElidedLabel(event.title)
        title.setStyleSheet(f"color: {INK}; font-size: 12px; font-weight: 600;")
        text.addWidget(title)
        meta_text = QLabel(
            f"{short_date(event.start_at.date())} · {event.display_time_range()}"
        )
        meta_text.setStyleSheet(f"color: {FAINT}; font-size: 10px;")
        text.addWidget(meta_text)
        layout.addLayout(text, 1)

        chevron = QLabel()
        chevron.setPixmap(icons.icon("chevron-right", FAINT, 14).pixmap(14, 14))
        chevron.setFixedSize(14, 14)
        layout.addWidget(chevron, 0, Qt.AlignmentFlag.AlignVCenter)

    def mouseReleaseEvent(self, event: QEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self._event)
        super().mouseReleaseEvent(event)


class SearchPopup(QFrame):
    eventChosen = Signal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("SearchPopup")
        self.setFixedWidth(420)
        add_shadow(self, blur=34, y_offset=10, alpha=45)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(8, 8, 8, 8)
        self._layout.setSpacing(2)
        self.hide()

    def show_results(self, events: Iterable[Event], query: str) -> None:
        while self._layout.count():
            item = self._layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        header = SectionLabel(f"Results for “{query.strip()}”")
        header.setContentsMargins(8, 4, 8, 4)
        self._layout.addWidget(header)

        found = False
        for event in events:
            row = SearchRow(event)
            row.clicked.connect(self._choose)
            self._layout.addWidget(row)
            found = True
        if not found:
            empty = QLabel("No matching events yet.")
            empty.setStyleSheet(f"color: {FAINT}; padding: 14px 10px;")
            self._layout.addWidget(empty)
        self.adjustSize()
        self.show()
        self.raise_()

    def _choose(self, event: Event) -> None:
        self.hide()
        self._eventChosen.emit(event)


class Toast(QWidget):
    snoozed = Signal(object)
    opened = Signal(object)
    dismissed = Signal(object)

    def __init__(self, event: Event, parent: QWidget | None = None) -> None:
        flags = (
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        super().__init__(parent, flags)
        self._event = event
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setFixedWidth(430)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(18, 18, 18, 18)
        container = QFrame()
        container.setObjectName("Toast")
        add_shadow(container, blur=38, y_offset=10, alpha=55)
        outer.addWidget(container)

        body = QHBoxLayout(container)
        body.setContentsMargins(14, 14, 12, 14)
        body.setSpacing(12)
        meta = event.category_meta

        bar = QFrame()
        bar.setFixedWidth(4)
        bar.setStyleSheet(f"background: {meta.color}; border-radius: 2px;")
        body.addWidget(bar)

        icon_circle = QLabel()
        icon_circle.setFixedSize(38, 38)
        icon_circle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_circle.setPixmap(icons.icon("bell", meta.color, 19).pixmap(19, 19))
        icon_circle.setStyleSheet(
            f"background: {meta.soft_color}; border-radius: 19px;"
        )
        body.addWidget(icon_circle, 0, Qt.AlignmentFlag.AlignTop)

        content = QVBoxLayout()
        content.setSpacing(3)
        kicker = QLabel("EVENT REMINDER")
        kicker.setStyleSheet(
            f"color: {meta.color}; font-size: 9px; font-weight: 800; letter-spacing: 1px;"
        )
        content.addWidget(kicker)
        title = QLabel(event.title)
        title.setWordWrap(True)
        title.setStyleSheet(f"color: {INK}; font-size: 14px; font-weight: 700;")
        content.addWidget(title)
        detail = QLabel(event.notification_body())
        detail.setWordWrap(True)
        detail.setStyleSheet(f"color: {MUTED}; font-size: 11px;")
        content.addWidget(detail)
        if event.description:
            note = QLabel(event.short_description(120))
            note.setWordWrap(True)
            note.setStyleSheet(f"color: {FAINT}; font-size: 11px;")
            content.addWidget(note)

        actions = QHBoxLayout()
        actions.setSpacing(6)
        open_button = QPushButton("Open event")
        open_button.setProperty("variant", "secondary")
        open_button.setCursor(Qt.CursorShape.PointingHandCursor)
        open_button.setStyleSheet("padding: 5px 11px; font-size: 11px;")
        open_button.clicked.connect(self._open)
        actions.addWidget(open_button)
        snooze = QPushButton("Snooze 10 min")
        snooze.setProperty("variant", "ghost")
        snooze.setCursor(Qt.CursorShape.PointingHandCursor)
        snooze.setStyleSheet("padding: 5px 8px; font-size: 11px;")
        snooze.clicked.connect(self._snooze)
        actions.addWidget(snooze)
        actions.addStretch(1)
        content.addLayout(actions)
        body.addLayout(content, 1)

        close = IconButton("close", size=26, icon_size=13, color=FAINT, tooltip="Dismiss")
        close.clicked.connect(self._dismiss)
        body.addWidget(close, 0, Qt.AlignmentFlag.AlignTop)

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(20000)
        self._timer.timeout.connect(self._dismiss)
        self._fade: QPropertyAnimation | None = None

    def present(self, bottom_right: QPoint, stack_index: int = 0) -> None:
        self.adjustSize()
        x = bottom_right.x() - self.width()
        y = bottom_right.y() - self.height() - stack_index * (self.height() + 10)
        screen = QGuiApplication.screenAt(bottom_right) or QGuiApplication.primaryScreen()
        if screen is not None:
            available = screen.availableGeometry()
            x = max(available.left() + 10, x)
            y = max(available.top() + 10, y)
        self.move(x, y)
        self.setWindowOpacity(0.0)
        self.show()
        self.raise_()
        self._fade = QPropertyAnimation(self, b"windowOpacity", self)
        self._fade.setDuration(180)
        self._fade.setStartValue(0.0)
        self._fade.setEndValue(1.0)
        self._fade.start()
        self._timer.start()

    def enterEvent(self, event: QEvent) -> None:  # noqa: N802
        self._timer.stop()
        super().enterEvent(event)

    def leaveEvent(self, event: QEvent) -> None:  # noqa: N802
        self._timer.start()
        super().leaveEvent(event)

    def _snooze(self) -> None:
        self.snoozed.emit(self._event)
        self._dismiss()

    def _open(self) -> None:
        self.opened.emit(self._event)
        self._dismiss()

    def _dismiss(self) -> None:
        self._timer.stop()
        self.dismissed.emit(self._event)
        self.close()

    def closeEvent(self, event: QEvent) -> None:  # noqa: N802
        self._timer.stop()
        super().closeEvent(event)


def shadow_color(hex_color: str) -> QColor:
    return QColor(hex_color)


class Notice(QWidget):
    """Small floating confirmation that does not interrupt the workflow."""

    def __init__(self, parent: QWidget | None = None) -> None:
        flags = (
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        super().__init__(parent, flags)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setFixedWidth(360)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 16, 16, 16)
        container = QFrame()
        container.setObjectName("Toast")
        add_shadow(container, blur=30, y_offset=8, alpha=45)
        outer.addWidget(container)
        layout = QHBoxLayout(container)
        layout.setContentsMargins(12, 10, 14, 10)
        layout.setSpacing(10)
        self._icon = QLabel()
        self._icon.setFixedSize(28, 28)
        self._icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._icon)
        self._text = QLabel()
        self._text.setWordWrap(True)
        self._text.setStyleSheet(f"color: {INK}; font-size: 11px; font-weight: 600;")
        layout.addWidget(self._text, 1)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(3600)
        self._timer.timeout.connect(self._dismiss)
        self._fade: QPropertyAnimation | None = None

    def show_message(
        self, message: str, *, kind: str = "success", anchor: QPoint | None = None
    ) -> None:
        color = "#0E9F6E" if kind == "success" else "#DC2626"
        soft = "#E7F8F1" if kind == "success" else "#FDECEC"
        icon_name = "check-circle" if kind == "success" else "info"
        self._icon.setPixmap(icons.icon(icon_name, color, 16).pixmap(16, 16))
        self._icon.setStyleSheet(f"background: {soft}; border-radius: 14px;")
        self._text.setText(message)
        self.adjustSize()
        if anchor is not None:
            x = anchor.x() - self.width() // 2
            y = anchor.y() - self.height()
            screen = QGuiApplication.screenAt(anchor) or QGuiApplication.primaryScreen()
            if screen is not None:
                available = screen.availableGeometry()
                x = max(available.left() + 12, min(x, available.right() - self.width() - 12))
                y = max(available.top() + 12, y)
            self.move(x, y)
        self.setWindowOpacity(0.0)
        self.show()
        self.raise_()
        self._fade = QPropertyAnimation(self, b"windowOpacity", self)
        self._fade.setDuration(160)
        self._fade.setStartValue(0.0)
        self._fade.setEndValue(1.0)
        self._fade.start()
        self._timer.start()

    def _dismiss(self) -> None:
        self.hide()
