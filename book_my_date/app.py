"""Application bootstrap: logging, theme, single-instance guard and window."""

from __future__ import annotations

import argparse
import logging
import logging.handlers
import sys
import traceback

from PySide6.QtCore import QCoreApplication, Qt
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import QApplication, QMessageBox

from .config import APP_ID, APP_NAME, VERSION, db_path, ensure_app_dirs, log_path
from .core.database import Database
from .core.reminders import ReminderEngine
from .ui import icons
from .ui.main_window import MainWindow
from .ui.theme import apply_theme

LOGGER = logging.getLogger(__name__)
SERVER_NAME = "book-my-date-single-instance"


def _configure_logging() -> None:
    ensure_app_dirs()
    handler = logging.handlers.RotatingFileHandler(
        log_path(),
        maxBytes=1_000_000,
        backupCount=3,
        encoding="utf-8",
    )
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(handler)
    if sys.stderr is not None:
        console = logging.StreamHandler()
        console.setLevel(logging.WARNING)
        console.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
        root.addHandler(console)


def _install_exception_hook() -> None:
    def handle(exc_type, exc_value, exc_tb):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_tb)
            return
        text = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        LOGGER.error("Unhandled exception:\n%s", text)
        try:
            QMessageBox.critical(
                None,
                f"{APP_NAME} hit an unexpected error",
                "Something went wrong, but your calendar is safe.\n\n"
                f"{exc_value}\n\nDetails were written to:\n{log_path()}",
            )
        except Exception:  # pragma: no cover - last-ditch safety
            sys.__excepthook__(exc_type, exc_value, exc_tb)

    sys.excepthook = handle


def _try_single_instance() -> QLocalSocket | None:
    socket = QLocalSocket()
    socket.connectToServer(SERVER_NAME)
    if socket.waitForConnected(250):
        socket.write(b"show")
        socket.flush()
        socket.waitForBytesWritten(250)
        socket.disconnectFromServer()
        return socket
    return None


def _serve_single_instance(window: MainWindow) -> QLocalServer | None:
    QLocalServer.removeServer(SERVER_NAME)
    server = QLocalServer()
    if not server.listen(SERVER_NAME):
        LOGGER.warning("Could not start single-instance server: %s", server.errorString())
        return None

    def accept() -> None:
        connection = server.nextPendingConnection()
        if connection is None:
            return
        connection.waitForReadyRead(120)
        connection.readAll()
        window._show_window()
        connection.disconnectFromServer()
        connection.deleteLater()

    server.newConnection.connect(accept)
    return server


def _set_windows_app_id() -> None:
    if sys.platform != "win32":
        return
    try:
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)
    except Exception:  # pragma: no cover - cosmetic only
        LOGGER.debug("Could not set Windows AppUserModelID", exc_info=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="book-my-date", description=APP_NAME)
    parser.add_argument("--version", action="store_true", help="print the version and exit")
    parser.add_argument(
        "--data-dir",
        help="override the local data directory (useful for testing)",
    )
    args, qt_args = parser.parse_known_args(argv)

    if args.version:
        print(f"{APP_NAME} {VERSION}")
        return 0

    if args.data_dir:
        import os

        os.environ["BOOK_MY_DATE_HOME"] = args.data_dir

    _configure_logging()
    _set_windows_app_id()

    QApplication.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps, True)
    QCoreApplication.setOrganizationName("BookMyDate")
    QCoreApplication.setOrganizationDomain("bookmydate.io")
    QCoreApplication.setApplicationName(APP_NAME)
    QCoreApplication.setApplicationVersion(VERSION)
    app = QApplication([sys.argv[0], *qt_args])
    app.setApplicationDisplayName(APP_NAME)
    app.setDesktopFileName("book-my-date")
    app.setQuitOnLastWindowClosed(True)
    app.setWindowIcon(icons.app_icon())
    _install_exception_hook()

    existing = _try_single_instance()
    if existing is not None:
        LOGGER.info("Another instance is running; asked it to show the window.")
        return 0

    try:
        database = Database(db_path())
    except Exception as exc:
        LOGGER.exception("Could not open the calendar database")
        QMessageBox.critical(
            None,
            APP_NAME,
            f"Book My Date could not open its database.\n\n{exc}",
        )
        return 1

    accent = database.get_setting("accent", "indigo") or "indigo"
    apply_theme(app, accent)
    app.setWindowIcon(icons.app_icon())

    engine = ReminderEngine(database)
    window = MainWindow(database, engine)
    server = _serve_single_instance(window)
    window.show()
    window.raise_()

    app.aboutToQuit.connect(database.close)
    exit_code = app.exec()
    if server is not None:
        server.close()
    return int(exit_code)
