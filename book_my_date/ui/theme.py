"""Visual design tokens and the global Qt stylesheet."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtGui import QColor, QFont, QFontDatabase, QPalette
from PySide6.QtWidgets import QApplication

FONT_CANDIDATES = (
    "Inter",
    "SF Pro Display",
    "Segoe UI Variable Display",
    "Segoe UI",
    "Ubuntu",
    "Noto Sans",
    "Cantarell",
    "DejaVu Sans",
)

BG = "#F3F5FA"
SURFACE = "#FFFFFF"
SURFACE_SOFT = "#F8FAFD"
INK = "#161D2F"
MUTED = "#6C7488"
FAINT = "#9AA3B5"
BORDER = "#E5E9F2"
BORDER_STRONG = "#D5DBE8"
SIDEBAR = "#121827"
SIDEBAR_CARD = "#1B2338"
SIDEBAR_TEXT = "#E9ECF6"
SIDEBAR_MUTED = "#8C96B0"
SATURDAY_BG = "#FFF8EE"
SATURDAY_INK = "#B45309"
SUNDAY_BG = "#FFF5F8"
SUNDAY_INK = "#BE185D"
OUTSIDE_BG = "#FAFBFD"
DANGER = "#DC2626"
DANGER_SOFT = "#FDECEC"
SUCCESS = "#0E9F6E"


@dataclass(frozen=True)
class Accent:
    key: str
    label: str
    color: str
    hover: str
    pressed: str
    soft: str
    ring: str


ACCENTS: dict[str, Accent] = {
    "indigo": Accent("indigo", "Indigo", "#5B5BD6", "#4B4BC4", "#3F3FB0", "#EEEFFE", "#C7C8F8"),
    "emerald": Accent("emerald", "Emerald", "#0E9F6E", "#0B8A5F", "#08724F", "#E7F8F1", "#B7EAD8"),
    "ocean": Accent("ocean", "Ocean", "#0E7490", "#0B6179", "#084E62", "#E6F6F9", "#B7E3EC"),
    "rose": Accent("rose", "Rose", "#E11D74", "#C41663", "#A51253", "#FDEBF3", "#F7BED8"),
}

DEFAULT_ACCENT = "indigo"


def accent_for(key: str) -> Accent:
    return ACCENTS.get(key, ACCENTS[DEFAULT_ACCENT])


def pick_font_family() -> str:
    available = set(QFontDatabase.families())
    for family in FONT_CANDIDATES:
        if family in available:
            return family
    return QFont().defaultFamily()


def build_stylesheet(accent_key: str = DEFAULT_ACCENT) -> str:
    accent = accent_for(accent_key)
    family = pick_font_family()
    return f"""
* {{
    outline: none;
}}
QWidget {{
    color: {INK};
    font-family: "{family}";
    font-size: 13px;
}}
QMainWindow, QDialog {{
    background: {BG};
}}
QWidget#Root {{
    background: {BG};
}}
QFrame#Card {{
    background: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 18px;
}}
QFrame#SoftCard {{
    background: {SURFACE_SOFT};
    border: 1px solid {BORDER};
    border-radius: 14px;
}}
QFrame#Sidebar {{
    background: {SIDEBAR};
    border: none;
}}
QFrame#Sidebar QLabel {{
    color: {SIDEBAR_TEXT};
    background: transparent;
}}
QFrame#Sidebar QLabel#SidebarMuted {{
    color: {SIDEBAR_MUTED};
}}
QFrame#Sidebar QLabel#SidebarSection {{
    color: {SIDEBAR_MUTED};
    font-size: 10px;
    font-weight: 700;
}}
QFrame#SidebarCard {{
    background: {SIDEBAR_CARD};
    border: 1px solid #27314A;
    border-radius: 12px;
}}
QFrame#SidebarCard:hover {{
    background: #222C45;
    border-color: #34405E;
}}
QFrame#SidebarCard QLabel {{
    background: transparent;
}}
QFrame#SidebarDivider {{
    background: #27314A;
    max-height: 1px;
    min-height: 1px;
    border: none;
}}
QLabel {{
    background: transparent;
}}
QLabel#PageTitle {{
    font-size: 23px;
    font-weight: 700;
    color: {INK};
}}
QLabel#DialogTitle {{
    font-size: 21px;
    font-weight: 700;
    color: {INK};
}}
QLabel#SectionLabel {{
    color: {FAINT};
    font-size: 10px;
    font-weight: 700;
}}
QLabel#Muted {{
    color: {MUTED};
}}
QLabel#Faint {{
    color: {FAINT};
}}
QLabel#FieldLabel {{
    color: {MUTED};
    font-size: 12px;
    font-weight: 600;
}}
QLabel#ErrorBanner {{
    background: {DANGER_SOFT};
    color: #B91C1C;
    border: 1px solid #F6C9C9;
    border-radius: 9px;
    padding: 9px 12px;
}}
QLabel#SuccessBanner {{
    background: #E9F9F1;
    color: #08724F;
    border: 1px solid #BFEAD8;
    border-radius: 9px;
    padding: 9px 12px;
}}
QPushButton {{
    border: 1px solid transparent;
    border-radius: 10px;
    padding: 9px 16px;
    font-weight: 600;
    background: transparent;
}}
QPushButton:hover {{
    background: {SURFACE_SOFT};
}}
QPushButton:pressed {{
    background: #EEF1F7;
}}
QPushButton[variant="primary"] {{
    background: {accent.color};
    color: #FFFFFF;
    border: 1px solid {accent.color};
    padding: 10px 18px;
}}
QPushButton[variant="primary"]:hover {{
    background: {accent.hover};
    border-color: {accent.hover};
}}
QPushButton[variant="primary"]:pressed {{
    background: {accent.pressed};
}}
QPushButton[variant="primary"]:disabled {{
    background: #B9C0D0;
    border-color: #B9C0D0;
}}
QPushButton[variant="secondary"] {{
    background: {SURFACE};
    color: {INK};
    border: 1px solid {BORDER_STRONG};
}}
QPushButton[variant="secondary"]:hover {{
    background: {SURFACE_SOFT};
    border-color: {accent.ring};
}}
QPushButton[variant="ghost"] {{
    background: transparent;
    color: {MUTED};
    border: none;
}}
QPushButton[variant="ghost"]:hover {{
    background: {SURFACE_SOFT};
    color: {INK};
}}
QPushButton[variant="danger"] {{
    background: {DANGER_SOFT};
    color: {DANGER};
    border: 1px solid #F6C9C9;
}}
QPushButton[variant="danger"]:hover {{
    background: #FBDDDD;
}}
QPushButton[variant="sidebar"] {{
    background: {SIDEBAR_CARD};
    color: {SIDEBAR_TEXT};
    border: 1px solid #27314A;
    text-align: left;
    padding: 10px 12px;
}}
QPushButton[variant="sidebar"]:hover {{
    background: #222C45;
    border-color: {accent.color};
}}
QPushButton#IconButton {{
    background: transparent;
    border: none;
    border-radius: 9px;
    padding: 0px;
}}
QPushButton#IconButton:hover {{
    background: {SURFACE_SOFT};
}}
QPushButton#IconButton:pressed {{
    background: #EAEEF6;
}}
QPushButton#SidebarIconButton {{
    background: transparent;
    border: none;
    border-radius: 9px;
    padding: 0px;
}}
QPushButton#SidebarIconButton:hover {{
    background: #222C45;
}}
QLineEdit, QTextEdit, QPlainTextEdit, QComboBox, QDateEdit, QTimeEdit, QSpinBox {{
    background: {SURFACE};
    border: 1px solid {BORDER_STRONG};
    border-radius: 10px;
    padding: 9px 11px;
    selection-background-color: {accent.color};
    selection-color: #FFFFFF;
}}
QLineEdit:hover, QTextEdit:hover, QPlainTextEdit:hover, QComboBox:hover,
QDateEdit:hover, QTimeEdit:hover {{
    border-color: {FAINT};
}}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QComboBox:focus,
QDateEdit:focus, QTimeEdit:focus {{
    border: 1px solid {accent.color};
    background: {SURFACE};
}}
QLineEdit:disabled, QComboBox:disabled, QDateEdit:disabled, QTimeEdit:disabled {{
    background: #F1F3F8;
    color: {FAINT};
}}
QLineEdit#SearchBox {{
    background: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 12px;
    padding: 9px 14px;
}}
QLineEdit#SearchBox:focus {{
    border: 1px solid {accent.color};
}}
QComboBox::drop-down, QDateEdit::drop-down, QTimeEdit::drop-down {{
    border: none;
    width: 26px;
    subcontrol-origin: padding;
    subcontrol-position: center right;
}}
QComboBox QAbstractItemView {{
    background: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 10px;
    padding: 5px;
    selection-background-color: {accent.soft};
    selection-color: {INK};
    outline: none;
}}
QComboBox QAbstractItemView::item {{
    min-height: 28px;
    padding: 4px 8px;
    border-radius: 6px;
}}
QDateEdit QCalendarWidget QWidget {{
    alternate-background-color: {SURFACE_SOFT};
}}
QCalendarWidget QToolButton {{
    color: {INK};
    background: transparent;
    border: none;
    border-radius: 6px;
    padding: 5px 8px;
    font-weight: 600;
}}
QCalendarWidget QToolButton:hover {{
    background: {accent.soft};
}}
QCalendarWidget QMenu {{
    background: {SURFACE};
}}
QCalendarWidget QSpinBox {{
    padding: 3px 6px;
}}
QCalendarWidget QAbstractItemView:enabled {{
    background: {SURFACE};
    color: {INK};
    selection-background-color: {accent.color};
    selection-color: #FFFFFF;
    outline: none;
}}
QCalendarWidget QAbstractItemView:disabled {{
    color: {FAINT};
}}
QCheckBox, QRadioButton {{
    spacing: 9px;
    color: {INK};
}}
QCheckBox::indicator, QRadioButton::indicator {{
    width: 18px;
    height: 18px;
    border: 1px solid {BORDER_STRONG};
    background: {SURFACE};
}}
QCheckBox::indicator {{
    border-radius: 5px;
}}
QRadioButton::indicator {{
    border-radius: 9px;
}}
QCheckBox::indicator:checked, QRadioButton::indicator:checked {{
    background: {accent.color};
    border-color: {accent.color};
}}
QCheckBox::indicator:hover, QRadioButton::indicator:hover {{
    border-color: {accent.color};
}}
QScrollArea {{
    background: transparent;
    border: none;
}}
QScrollArea > QWidget > QWidget {{
    background: transparent;
}}
QScrollBar:vertical {{
    background: transparent;
    width: 10px;
    margin: 2px;
}}
QScrollBar::handle:vertical {{
    background: #C9D0DE;
    border-radius: 4px;
    min-height: 36px;
}}
QScrollBar::handle:vertical:hover {{
    background: #AEB7C9;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
    background: none;
    height: 0px;
}}
QScrollBar:horizontal {{
    background: transparent;
    height: 10px;
    margin: 2px;
}}
QScrollBar::handle:horizontal {{
    background: #C9D0DE;
    border-radius: 4px;
    min-width: 36px;
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal,
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
    background: none;
    width: 0px;
}}
QToolTip {{
    background: {INK};
    color: #FFFFFF;
    border: none;
    border-radius: 6px;
    padding: 6px 9px;
}}
QMenu {{
    background: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 10px;
    padding: 6px;
}}
QMenu::item {{
    padding: 7px 22px 7px 12px;
    border-radius: 6px;
}}
QMenu::item:selected {{
    background: {accent.soft};
    color: {INK};
}}
QMenu::separator {{
    height: 1px;
    background: {BORDER};
    margin: 5px 8px;
}}
QMessageBox {{
    background: {SURFACE};
}}
QMessageBox QLabel {{
    color: {INK};
}}
QFrame#EventCard {{
    background: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 13px;
}}
QFrame#EventCard:hover {{
    border-color: {accent.ring};
    background: #FDFDFF;
}}
QFrame#EventChip {{
    border-radius: 6px;
    border: none;
}}
QFrame#EventChip:hover {{
    background: #EDF1F8;
}}
QFrame#Toast {{
    background: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 16px;
}}
QFrame#Toast QLabel {{
    background: transparent;
}}
QFrame#Badge {{
    border-radius: 7px;
    padding: 2px 7px;
}}
QFrame#Divider {{
    background: {BORDER};
    max-height: 1px;
    min-height: 1px;
    border: none;
}}
QFrame#ToastDivider {{
    background: {BORDER};
    max-height: 1px;
    min-height: 1px;
    border: none;
}}
QWidget#CalendarCard {{
    background: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 18px;
}}
QWidget#DayCell {{
    background: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 10px;
}}
QWidget#DayCell:hover {{
    border-color: {FAINT};
}}
QWidget#DayCell[weekend="sat"] {{
    background: {SATURDAY_BG};
    border-color: #F6E4CC;
}}
QWidget#DayCell[weekend="sun"] {{
    background: {SUNDAY_BG};
    border-color: #F7DDE7;
}}
QWidget#DayCell[outside="true"] {{
    background: {OUTSIDE_BG};
    border-color: #EEF1F6;
}}
QWidget#DayCell[selected="true"] {{
    border: 2px solid {accent.color};
}}
QWidget#DayCell[today="true"] {{
    background: {accent.soft};
    border: 1px solid {accent.ring};
}}
QWidget#DayCell[weekend="sat"][today="true"] {{
    background: #FFF1DC;
    border: 1px solid {SATURDAY_INK};
}}
QWidget#DayCell[weekend="sun"][today="true"] {{
    background: #FDE9F0;
    border: 1px solid {SUNDAY_INK};
}}
QWidget#DayCell QLabel {{
    background: transparent;
}}
QLabel#DayNumber {{
    color: {INK};
    font-size: 13px;
    font-weight: 600;
    border-radius: 13px;
    padding: 1px 2px;
}}
QWidget#DayCell[outside="true"] QLabel#DayNumber {{
    color: #B7BFCD;
}}
QWidget#DayCell[weekend="sat"] QLabel#DayNumber {{
    color: {SATURDAY_INK};
}}
QWidget#DayCell[weekend="sun"] QLabel#DayNumber {{
    color: {SUNDAY_INK};
}}
QLabel#TodayNumber {{
    background: {accent.color};
    color: #FFFFFF;
    font-size: 12px;
    font-weight: 700;
    border-radius: 13px;
    padding: 1px 2px;
}}
QLabel#MoreLabel {{
    color: {MUTED};
    font-size: 10px;
    font-weight: 600;
    padding-left: 4px;
}}
QLabel#WeekendHeader {{
    color: {MUTED};
    font-size: 10px;
    font-weight: 700;
}}
QLabel#WeekendHeader[weekend="sat"] {{
    color: {SATURDAY_INK};
    background: #FFF2E0;
    border-radius: 6px;
}}
QLabel#WeekendHeader[weekend="sun"] {{
    color: {SUNDAY_INK};
    background: #FDE9F0;
    border-radius: 6px;
}}
QFrame#SearchPopup {{
    background: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 14px;
}}
QFrame#SearchRow {{
    background: transparent;
    border: none;
    border-radius: 9px;
}}
QFrame#SearchRow:hover {{
    background: {SURFACE_SOFT};
}}
QListWidget {{
    background: transparent;
    border: none;
    outline: none;
}}
QListWidget::item {{
    border-radius: 8px;
    padding: 6px;
}}
QListWidget::item:selected {{
    background: {accent.soft};
    color: {INK};
}}
QListWidget::item:hover {{
    background: {SURFACE_SOFT};
}}
QToolButton {{
    border: none;
    background: transparent;
    border-radius: 8px;
    padding: 5px;
}}
QToolButton:hover {{
    background: {SURFACE_SOFT};
}}
"""


def apply_theme(app: QApplication, accent_key: str = DEFAULT_ACCENT) -> None:
    app.setStyle("Fusion")
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(BG))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(INK))
    palette.setColor(QPalette.ColorRole.Base, QColor(SURFACE))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(SURFACE_SOFT))
    palette.setColor(QPalette.ColorRole.Text, QColor(INK))
    palette.setColor(QPalette.ColorRole.Button, QColor(SURFACE))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(INK))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(accent_for(accent_key).color))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#FFFFFF"))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(INK))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor("#FFFFFF"))
    app.setPalette(palette)
    font = QFont(pick_font_family())
    font.setPointSizeF(10.3)
    app.setFont(font)
    app.setStyleSheet(build_stylesheet(accent_key))


def repolish(widget: object) -> None:
    style = widget.style()  # type: ignore[attr-defined]
    style.unpolish(widget)
    style.polish(widget)
    widget.update()  # type: ignore[attr-defined]
