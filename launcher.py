#!/usr/bin/env python3
"""Click launcher for Book My Date.

The launcher uses only the standard library. On the first run it opens the
browser setup wizard; once the app is installed it starts the private
environment created by that wizard.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
WIZARD = ROOT / "installer" / "wizard.py"


def install_root() -> Path:
    override = os.environ.get("BOOK_MY_DATE_HOME")
    if override:
        return Path(override).expanduser()
    if sys.platform == "win32":
        return Path.home() / "BookMyDate"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "BookMyDate"
    base = os.environ.get("XDG_DATA_HOME")
    root = Path(base) if base else Path.home() / ".local" / "share"
    return root / "book-my-date"


def _venv_python(root: Path) -> Path:
    if os.name == "nt":
        pythonw = root / "venv" / "Scripts" / "pythonw.exe"
        if pythonw.exists():
            return pythonw
        return root / "venv" / "Scripts" / "python.exe"
    return root / "venv" / "bin" / "python"


def _install_record(root: Path) -> dict:
    try:
        return json.loads((root / "install.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _is_installed(root: Path) -> bool:
    record = _install_record(root)
    app_dir = Path(str(record.get("app_dir") or root / "app")).expanduser()
    return (
        (root / "install.json").exists()
        and (app_dir / "book_my_date" / "__main__.py").exists()
        and _venv_python(root).exists()
    )


def _check_qt(python: Path, app_dir: Path) -> tuple[bool, str]:
    code = (
        "import os\n"
        "os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')\n"
        "from PySide6.QtWidgets import QApplication\n"
        "app = QApplication([])\n"
        "print('ok')\n"
    )
    env = os.environ.copy()
    env["BOOK_MY_DATE_HOME"] = str(install_root())
    env["QT_QPA_PLATFORM"] = "offscreen"
    env.pop("PYTHONPATH", None)
    env.pop("PYTHONHOME", None)
    try:
        result = subprocess.run(
            [str(python), "-c", code],
            cwd=str(app_dir),
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return False, str(exc)
    if result.returncode == 0:
        return True, ""
    detail = (result.stderr or result.stdout or "").strip()
    return False, detail[-1200:]


def _launch_installed(root: Path) -> bool:
    record = _install_record(root)
    app_dir = Path(str(record.get("app_dir") or root / "app")).expanduser()
    python = _venv_python(root)
    if not _is_installed(root):
        return False

    ok, detail = _check_qt(python, app_dir)
    if not ok:
        print("Book My Date is installed, but its interface could not start.")
        if detail:
            print(detail)
        print("Opening setup so it can be repaired.")
        return False

    env = os.environ.copy()
    env["BOOK_MY_DATE_HOME"] = str(root)
    env.pop("PYTHONPATH", None)
    env.pop("PYTHONHOME", None)
    kwargs: dict = {
        "cwd": str(app_dir),
        "env": env,
        "stdin": subprocess.DEVNULL,
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
        "close_fds": True,
    }
    if os.name == "nt":
        kwargs["creationflags"] = getattr(
            subprocess, "DETACHED_PROCESS", 0
        ) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    else:
        kwargs["start_new_session"] = True
    try:
        subprocess.Popen([str(python), "-m", "book_my_date"], **kwargs)
    except OSError as exc:
        print(f"Could not open Book My Date: {exc}")
        return False
    return True


def _run_wizard(*, no_browser: bool = False, port: int | None = None) -> int:
    if not WIZARD.exists():
        print(f"Setup wizard not found at {WIZARD}")
        return 1
    command = [sys.executable, str(WIZARD)]
    if no_browser:
        command.append("--no-browser")
    if port is not None:
        command.extend(["--port", str(port)])
    try:
        return subprocess.call(command)
    except OSError as exc:
        print(f"Could not start setup: {exc}")
        return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Open Book My Date or its setup")
    parser.add_argument(
        "--setup",
        action="store_true",
        help="always open the setup/repair wizard",
    )
    parser.add_argument("--no-browser", action="store_true", help="do not open a browser")
    parser.add_argument("--port", type=int, help="setup wizard port")
    parser.add_argument(
        "--data-dir",
        help="override the local data and installation directory",
    )
    args = parser.parse_args(argv)

    if args.data_dir:
        os.environ["BOOK_MY_DATE_HOME"] = str(Path(args.data_dir).expanduser())

    root = install_root()
    if not args.setup and _launch_installed(root):
        return 0
    return _run_wizard(no_browser=args.no_browser, port=args.port)


if __name__ == "__main__":
    raise SystemExit(main())
