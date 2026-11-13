"""Application paths, metadata and platform helpers."""

from __future__ import annotations

import os
import sys
from pathlib import Path

APP_NAME = "Book My Date"
APP_SLUG = "book-my-date"
APP_ID = "io.bookmydate.app"
VERSION = "1.0.0"
DB_FILENAME = "book_my_date.db"
LOG_FILENAME = "book_my_date.log"

__all__ = [
    "APP_NAME",
    "APP_SLUG",
    "APP_ID",
    "VERSION",
    "DB_FILENAME",
    "LOG_FILENAME",
    "app_data_dir",
    "db_path",
    "log_path",
    "ensure_app_dirs",
    "asset_path",
    "assets_dir",
]


def app_data_dir() -> Path:
    """Return the per-user directory that holds the database and preferences."""

    override = os.environ.get("BOOK_MY_DATE_HOME")
    if override:
        return Path(override).expanduser()

    if sys.platform == "win32":
        return Path.home() / "BookMyDate"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "BookMyDate"

    base = os.environ.get("XDG_DATA_HOME")
    root = Path(base) if base else Path.home() / ".local" / "share"
    return root / APP_SLUG


def ensure_app_dirs() -> Path:
    path = app_data_dir()
    path.mkdir(parents=True, exist_ok=True)
    return path


def db_path() -> Path:
    return app_data_dir() / DB_FILENAME


def log_path() -> Path:
    return app_data_dir() / LOG_FILENAME


def assets_dir() -> Path:
    """Location of bundled assets in source checkouts and frozen bundles."""

    frozen_root = getattr(sys, "_MEIPASS", None)
    if frozen_root:
        return Path(frozen_root) / "book_my_date" / "assets"
    return Path(__file__).resolve().parent / "assets"


def asset_path(name: str) -> Path:
    return assets_dir() / name
