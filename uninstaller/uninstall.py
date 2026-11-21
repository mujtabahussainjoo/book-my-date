#!/usr/bin/env python3
"""Remove the installed Book My Date app, its shortcuts and optionally its data.

The uninstaller uses only the Python standard library so it can run before the
app's private virtual environment exists (for example after a broken install).
It never touches the source checkout you launch it from.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import shutil
import signal
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

APP_NAME = "Book My Date"
LINUX_DESKTOP_FILE = "book-my-date.desktop"
LINUX_UNINSTALL_DESKTOP_FILE = "book-my-date-uninstall.desktop"
LINUX_COMMAND = "book-my-date"
LINUX_ICON = "book-my-date.png"
WINDOWS_SHORTCUT = "Book My Date.lnk"
WINDOWS_UNINSTALL_SHORTCUT = "Uninstall Book My Date.lnk"
MACOS_BUNDLE = "Book My Date.app"
MACOS_UNINSTALL_BUNDLE = "Uninstall Book My Date.app"

DATA_FILES = (
    "book_my_date.db",
    "book_my_date.db-wal",
    "book_my_date.db-shm",
    "book_my_date.log",
    "install.json",
    "install.log",
    "uninstall.py",
)
DATA_DIRECTORIES = ("backups",)


def install_root(platform_name: str | None = None) -> Path:
    """Return the data/install directory used by the launcher and wizard."""

    override = os.environ.get("BOOK_MY_DATE_HOME")
    if override:
        return Path(override).expanduser()
    current = platform_name or sys.platform
    if current == "win32":
        return Path.home() / "BookMyDate"
    if current == "darwin":
        return Path.home() / "Library" / "Application Support" / "BookMyDate"
    base = os.environ.get("XDG_DATA_HOME")
    return (Path(base) if base else Path.home() / ".local" / "share") / "book-my-date"


def candidate_roots(
    platform_name: str | None = None,
    override: str | None = None,
) -> list[Path]:
    """Return every standard install location, with an explicit override first."""

    current = platform_name or sys.platform
    roots: list[Path] = []
    if override:
        roots.append(Path(override).expanduser())
    elif os.environ.get("BOOK_MY_DATE_HOME"):
        roots.append(Path(os.environ["BOOK_MY_DATE_HOME"]).expanduser())

    if current == "win32":
        roots.append(Path.home() / "BookMyDate")
    elif current == "darwin":
        roots.append(Path.home() / "Library" / "Application Support" / "BookMyDate")
    else:
        base = os.environ.get("XDG_DATA_HOME")
        if base:
            roots.append(Path(base) / "book-my-date")
        roots.append(Path.home() / ".local" / "share" / "book-my-date")

    seen: set[str] = set()
    unique: list[Path] = []
    for root in roots:
        key = str(root.resolve())
        if key not in seen:
            seen.add(key)
            unique.append(root)
    return unique


def read_install_record(root: Path) -> dict:
    try:
        value = json.loads((root / "install.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


def _within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except (ValueError, OSError):
        return False
    return path.resolve() != root.resolve()


def _desktop_dir() -> Path | None:
    config = Path.home() / ".config" / "user-dirs.dirs"
    if config.exists():
        try:
            for line in config.read_text(encoding="utf-8").splitlines():
                if line.startswith("XDG_DESKTOP_DIR="):
                    value = line.split("=", 1)[1].strip().strip('"')
                    candidate = Path(value.replace("$HOME", str(Path.home()))).expanduser()
                    if candidate.exists():
                        return candidate
        except OSError:
            pass
    desktop = Path.home() / "Desktop"
    return desktop if desktop.exists() else None


def shortcut_paths(platform_name: str | None = None) -> list[Path]:
    current = platform_name or sys.platform
    if current == "win32":
        programs = Path(
            os.environ.get("APPDATA", str(Path.home() / "AppData" / "Roaming"))
        )
        menu = programs / "Microsoft" / "Windows" / "Start Menu" / "Programs"
        return [
            Path.home() / "Desktop" / WINDOWS_SHORTCUT,
            menu / WINDOWS_SHORTCUT,
            Path.home() / "Desktop" / WINDOWS_UNINSTALL_SHORTCUT,
            menu / WINDOWS_UNINSTALL_SHORTCUT,
        ]
    if current == "darwin":
        return [
            Path.home() / "Applications" / MACOS_BUNDLE,
            Path.home() / "Applications" / MACOS_UNINSTALL_BUNDLE,
            Path.home() / "Desktop" / MACOS_UNINSTALL_BUNDLE,
        ]
    paths = [
        Path.home() / ".local" / "share" / "applications" / LINUX_DESKTOP_FILE,
        Path.home() / ".local" / "share" / "applications" / LINUX_UNINSTALL_DESKTOP_FILE,
        Path.home() / ".local" / "bin" / LINUX_COMMAND,
        Path.home()
        / ".local"
        / "share"
        / "icons"
        / "hicolor"
        / "256x256"
        / "apps"
        / LINUX_ICON,
    ]
    desktop = _desktop_dir()
    if desktop is not None:
        paths.append(desktop / f"{APP_NAME}.desktop")
        paths.append(desktop / "Uninstall Book My Date.desktop")
    return paths


def _settings_paths(platform_name: str | None = None) -> list[Path]:
    current = platform_name or sys.platform
    if current == "darwin":
        return [Path.home() / "Library" / "Preferences" / "com.BookMyDate.BookMyDate.plist"]
    if current == "win32":
        return []
    return [Path.home() / ".config" / "BookMyDate" / "BookMyDate.conf"]


@dataclass
class UninstallPlan:
    root: Path
    files: list[Path] = field(default_factory=list)
    directories: list[Path] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    purge_data: bool = False

    def add_file(self, path: Path) -> None:
        if path not in self.files:
            self.files.append(path)

    def add_directory(self, path: Path) -> None:
        if path not in self.directories:
            self.directories.append(path)

    def describe(self) -> list[str]:
        lines = [f"Install directory: {self.root}"]
        if self.directories:
            lines.append("Folders:")
            lines.extend(f"  - {path}" for path in self.directories)
        if self.files:
            lines.append("Files:")
            lines.extend(f"  - {path}" for path in self.files)
        lines.extend(f"Warning: {warning}" for warning in self.warnings)
        return lines


def build_plan(
    root: Path,
    *,
    purge_data: bool = False,
    remove_shortcuts: bool = True,
    platform_name: str | None = None,
    record: dict | None = None,
) -> UninstallPlan:
    """Collect everything the uninstaller is allowed to delete."""

    current = platform_name or sys.platform
    details = read_install_record(root) if record is None else record
    plan = UninstallPlan(root=root, purge_data=purge_data)

    configured_app = details.get("app_dir")
    app_dir = (
        Path(str(configured_app)).expanduser() if configured_app else root / "app"
    )
    if _within(app_dir, root):
        plan.add_directory(app_dir)
    elif app_dir.exists():
        plan.warnings.append(
            f"Skipping app folder outside the install directory: {app_dir}"
        )

    venv_dir = root / "venv"
    if venv_dir.exists() or (root / "install.json").exists():
        plan.add_directory(venv_dir)

    plan.add_file(root / "install.json")
    plan.add_file(root / "install.log")

    if purge_data:
        for name in DATA_FILES:
            plan.add_file(root / name)
        for name in DATA_DIRECTORIES:
            plan.add_directory(root / name)
        for path in _settings_paths(current):
            plan.add_file(path)

    if remove_shortcuts:
        for path in shortcut_paths(current):
            if path.name.endswith(".app"):
                plan.add_directory(path)
            else:
                plan.add_file(path)
    return plan


def execute(plan: UninstallPlan, *, dry_run: bool = False) -> tuple[list[str], list[str]]:
    """Delete planned targets, returning actions and any failures."""

    actions: list[str] = []
    errors: list[str] = []

    def unlink(path: Path) -> None:
        if not (path.is_file() or path.is_symlink()):
            return
        actions.append(f"Removed file: {path}")
        if dry_run:
            return
        try:
            path.unlink()
        except OSError as exc:
            errors.append(f"Could not remove {path}: {exc}")

    def rmtree(path: Path) -> None:
        if path.is_symlink():
            unlink(path)
            return
        if not path.is_dir():
            return
        actions.append(f"Removed folder: {path}")
        if dry_run:
            return
        try:
            shutil.rmtree(path)
        except OSError as exc:
            errors.append(f"Could not remove {path}: {exc}")

    for path in sorted(plan.directories, key=lambda item: len(item.parts), reverse=True):
        rmtree(path)
    for path in plan.files:
        unlink(path)

    would_empty_root = plan.root.is_dir() and all(
        child in plan.files or child in plan.directories for child in plan.root.iterdir()
    )
    if plan.purge_data and would_empty_root:
        actions.append(f"Removed folder: {plan.root}")
        if not dry_run:
            try:
                plan.root.rmdir()
            except OSError as exc:
                errors.append(f"Could not remove {plan.root}: {exc}")
    return actions, errors


def _command_lines(platform_name: str) -> list[tuple[int, str]]:
    if platform_name == "win32":
        command = [
            "powershell",
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            "Get-CimInstance Win32_Process | ForEach-Object "
            '{ "$($_.ProcessId)`t$($_.CommandLine)" }',
        ]
    else:
        command = ["ps", "-eo", "pid=,args="]
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    lines: list[tuple[int, str]] = []
    for line in result.stdout.splitlines():
        parts = line.strip().split(None, 1)
        if len(parts) != 2 or not parts[0].isdigit():
            continue
        lines.append((int(parts[0]), parts[1]))
    return lines


def running_pids(
    root: Path,
    *,
    platform_name: str | None = None,
    record: dict | None = None,
) -> list[int]:
    """Find running app processes without depending on the app's environment."""

    current = platform_name or sys.platform
    details = read_install_record(root) if record is None else record
    tokens = [str(root / "venv"), str(root / "app"), "-m book_my_date"]
    if details.get("app_dir"):
        tokens.append(str(details["app_dir"]))
    found: list[int] = []
    for pid, command in _command_lines(current):
        if pid == os.getpid() or "uninstall" in command.lower():
            continue
        if any(token in command for token in tokens):
            found.append(pid)
    return found


def stop_processes(pids: list[int], platform_name: str | None = None) -> None:
    current = platform_name or sys.platform
    for pid in pids:
        if current == "win32":
            subprocess.run(
                ["taskkill", "/PID", str(pid), "/T", "/F"],
                capture_output=True,
                check=False,
            )
        else:
            with contextlib.suppress(ProcessLookupError, PermissionError):
                os.kill(pid, signal.SIGTERM)
    if pids:
        time.sleep(0.8)


def _unsafe_root(root: Path) -> bool:
    resolved = root.resolve()
    return resolved == Path.home().resolve() or resolved == Path(resolved.anchor)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=f"Uninstall {APP_NAME} from this computer."
    )
    parser.add_argument(
        "--data-dir",
        help="override the data and installation directory",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="check every standard install location for this operating system",
    )
    parser.add_argument(
        "--purge",
        action="store_true",
        help="also delete the calendar database, backups, log and preferences",
    )
    parser.add_argument(
        "--keep-data",
        action="store_true",
        help="keep the database even when the uninstaller was told to purge",
    )
    parser.add_argument(
        "--no-shortcuts",
        action="store_true",
        help="leave desktop, menu and application shortcuts in place",
    )
    parser.add_argument(
        "--yes",
        "-y",
        action="store_true",
        help="skip the confirmation prompt",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="stop a running app automatically instead of asking you to quit it",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="only list what would be removed",
    )
    args = parser.parse_args(argv)
    if args.keep_data:
        args.purge = False

    platform_name = sys.platform
    if args.all:
        roots = candidate_roots(platform_name, args.data_dir)
    else:
        if args.data_dir:
            os.environ["BOOK_MY_DATE_HOME"] = str(Path(args.data_dir).expanduser())
        roots = [install_root(platform_name)]
    unsafe = [root for root in roots if _unsafe_root(root)]
    roots = [root for root in roots if not _unsafe_root(root)]
    if not roots:
        print(f"Refusing to uninstall from an unsafe root: {unsafe[0]}")
        return 1

    records: dict[Path, dict] = {}
    pids: list[int] = []
    for root in roots:
        details = read_install_record(root)
        records[root] = details
        pids.extend(running_pids(root, platform_name=platform_name, record=details))
    pids = sorted(set(pids))
    if pids and not args.dry_run:
        if not args.force:
            print(
                f"{APP_NAME} is still running (PID {', '.join(str(pid) for pid in pids)})."
            )
            print("Quit it from the system tray, or rerun with --force.")
            return 1
        stop_processes(pids, platform_name)

    plans = [
        build_plan(
            root,
            purge_data=args.purge,
            remove_shortcuts=not args.no_shortcuts and index == 0,
            platform_name=platform_name,
            record=records[root],
        )
        for index, root in enumerate(roots)
    ]
    if args.dry_run:
        print("Dry run — nothing will be deleted.")
        for plan in plans:
            for line in plan.describe():
                print(line)
            print()
        return 0

    mode = "app, data and shortcuts" if args.purge else "app and shortcuts (data kept)"
    target = "all standard install locations" if len(roots) > 1 else str(roots[0])
    if not args.yes:
        if not sys.stdin.isatty():
            print("Pass --yes to confirm a non-interactive uninstall.")
            return 1
        answer = input(f"Remove {APP_NAME} ({mode}) from {target}? [y/N] ")
        if answer.strip().lower() not in {"y", "yes"}:
            print("Uninstall cancelled.")
            return 0

    actions: list[str] = []
    warnings: list[str] = []
    errors: list[str] = []
    for plan in plans:
        plan_actions, plan_errors = execute(plan)
        actions.extend(plan_actions)
        warnings.extend(plan.warnings)
        errors.extend(plan_errors)

    if not actions:
        print(f"No {APP_NAME} installation found at {target}.")
    for action in actions:
        print(action)
    for warning in warnings + errors:
        print(f"Warning: {warning}")
    if not errors:
        print(
            f"{APP_NAME} was removed."
            if args.purge
            else f"{APP_NAME} was removed. Your calendar data was kept."
        )
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
