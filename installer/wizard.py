#!/usr/bin/env python3
"""Click-to-install setup wizard for Book My Date.

The wizard uses only the Python standard library and a local web page, so it
works even on systems where Tk is not installed.  Double-clicking any of the
platform launchers in the repository root opens this wizard automatically.
"""

from __future__ import annotations

import argparse
import base64
import ctypes.util
import json
import os
import platform
import re
import shlex
import shutil
import sqlite3
import subprocess
import sys
import threading
import time
import traceback
import venv
import webbrowser
from dataclasses import dataclass, field
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parent.parent
REQUIREMENTS = "PySide6-Essentials>=6.8.3,<7"
ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
MAX_LOG_LINES = 400


def read_version() -> str:
    try:
        text = (ROOT / "book_my_date" / "config.py").read_text(encoding="utf-8")
        match = re.search(r'VERSION\s*=\s*"([^"]+)"', text)
        if match:
            return match.group(1)
    except OSError:
        pass
    return "1.0.0"


APP_VERSION = read_version()


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


def platform_label() -> str:
    if sys.platform == "win32":
        return f"Windows {platform.release()}"
    if sys.platform == "darwin":
        return f"macOS {platform.mac_ver()[0]}"
    try:
        name = platform.freedesktop_os_release().get("PRETTY_NAME", "Linux")
    except (OSError, AttributeError):
        name = "Linux"
    return name


def detect_missing_linux_libs() -> list[str]:
    if not sys.platform.startswith("linux"):
        return []
    missing: list[str] = []
    checks = (
        ("xcb-cursor", "libxcb-cursor0"),
        ("xkbcommon-x11", "libxkbcommon-x11-0"),
    )
    for library, package in checks:
        try:
            if ctypes.util.find_library(library) is None:
                missing.append(package)
        except OSError:
            missing.append(package)
    return missing


def _venv_python(venv_dir: Path) -> Path:
    if os.name == "nt":
        return venv_dir / "Scripts" / "python.exe"
    return venv_dir / "bin" / "python"


def _venv_pythonw(venv_dir: Path) -> Path:
    if os.name == "nt":
        candidate = venv_dir / "Scripts" / "pythonw.exe"
        if candidate.exists():
            return candidate
    return _venv_python(venv_dir)


def _desktop_quote(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


@dataclass
class InstallOptions:
    shortcuts: bool = True
    launch: bool = True


class InstallError(RuntimeError):
    pass


class Controller:
    def __init__(self) -> None:
        self.root = ROOT
        self.data_dir = install_root()
        self.app_dir = self.data_dir / "app"
        self.venv_dir = self.data_dir / "venv"
        self._lock = threading.RLock()
        self._thread: threading.Thread | None = None
        self._state: dict[str, Any] = {
            "status": "idle",
            "progress": 0,
            "message": "Ready when you are.",
            "error": "",
            "warnings": [],
            "log": [],
            "current_step": "",
            "steps": [
                {"key": "environment", "label": "Check your system", "status": "pending"},
                {"key": "files", "label": "Copy application files", "status": "pending"},
                {"key": "packages", "label": "Install dependencies", "status": "pending"},
                {"key": "shortcuts", "label": "Create shortcuts", "status": "pending"},
                {"key": "finish", "label": "Finish up", "status": "pending"},
            ],
            "version": APP_VERSION,
            "python_version": platform.python_version(),
            "python_ok": sys.version_info >= (3, 9),
            "platform": platform_label(),
            "existing": False,
            "installed_version": "",
            "launch_ready": False,
            "missing_libs": [],
            "libs_fixing": False,
            "lib_error": "",
            "data_dir": str(self.data_dir),
            "app_dir": str(self.app_dir),
            "venv_python": str(_venv_python(self.venv_dir)),
            "log_path": str(self.data_dir / "install.log"),
        }
        self._refresh_environment()

    # ------------------------------------------------------------------ state
    def _refresh_environment(self) -> None:
        install_file = self.data_dir / "install.json"
        installed_version = ""
        existing = False
        if install_file.exists() and (self.app_dir / "book_my_date").exists():
            existing = True
            try:
                installed_version = str(
                    json.loads(install_file.read_text(encoding="utf-8")).get(
                        "version", ""
                    )
                )
            except (OSError, ValueError):
                installed_version = ""
        missing = detect_missing_linux_libs()
        with self._lock:
            self._state["existing"] = existing
            self._state["installed_version"] = installed_version
            self._state["missing_libs"] = missing
            self._state["data_dir"] = str(self.data_dir)
            self._state["app_dir"] = str(self.app_dir)
            self._state["venv_python"] = str(_venv_python(self.venv_dir))
            if not self._state["python_ok"]:
                self._set_step("environment", "error", "Python 3.9 or newer is required.")

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                **{key: value for key, value in self._state.items()},
                "warnings": list(self._state["warnings"]),
                "log": list(self._state["log"]),
                "steps": [dict(step) for step in self._state["steps"]],
            }

    def _log(self, message: str) -> None:
        clean = ANSI_RE.sub("", str(message)).rstrip()
        if not clean:
            return
        stamp = datetime.now().strftime("%H:%M:%S")
        with self._lock:
            self._state["log"].append(f"[{stamp}] {clean}")
            if len(self._state["log"]) > MAX_LOG_LINES:
                del self._state["log"][: len(self._state["log"]) - MAX_LOG_LINES]

    def _warning(self, message: str) -> None:
        self._log(f"WARNING: {message}")
        with self._lock:
            if message not in self._state["warnings"]:
                self._state["warnings"].append(message)
                del self._state["warnings"][:-20]

    def _set(self, **values: Any) -> None:
        with self._lock:
            self._state.update(values)

    def _set_step(self, key: str, status: str, detail: str = "") -> None:
        with self._lock:
            for step in self._state["steps"]:
                if step["key"] == key:
                    step["status"] = status
                    if detail:
                        step["detail"] = detail
                    break
            self._state["current_step"] = key

    # ------------------------------------------------------------------ start
    def start(self, options: InstallOptions) -> bool:
        with self._lock:
            if self._state["status"] == "running":
                return False
            self._state.update(
                {
                    "status": "running",
                    "progress": 2,
                    "message": "Checking your system…",
                    "error": "",
                    "warnings": [],
                    "log": [],
                    "launch_ready": False,
                }
            )
            for step in self._state["steps"]:
                step["status"] = "pending"
                step.pop("detail", None)
        self._thread = threading.Thread(
            target=self._install, args=(options,), name="bmd-installer", daemon=True
        )
        self._thread.start()
        return True

    def _install(self, options: InstallOptions) -> None:
        started = time.time()
        try:
            self._log(f"Book My Date {APP_VERSION} setup started")
            self._log(f"Python {platform.python_version()} on {platform_label()}")
            if sys.version_info < (3, 9):  # noqa: UP036
                raise InstallError(
                    "Python 3.9 or newer is required. Please install a current "
                    "Python from python.org and run this launcher again."
                )
            self._set_step("environment", "done")
            self._set(progress=7, message="Preparing your private app folder…")

            self.data_dir.mkdir(parents=True, exist_ok=True)
            self._backup_database()

            self._set(progress=14, message="Copying application files…")
            self._copy_application()
            self._set_step("files", "done")
            self._set(progress=24, message="Creating an isolated Python environment…")

            python = self._ensure_venv()
            self._set(progress=38, message="Installing the interface toolkit…")
            self._install_dependencies(python)
            self._set_step("packages", "done")
            self._set(progress=88, message="Adding shortcuts…")

            if options.shortcuts:
                created = self._create_shortcuts(python)
                if created:
                    self._log("Created shortcuts: " + ", ".join(created))
                self._set_step("shortcuts", "done")
            else:
                self._set_step("shortcuts", "done", "Skipped")

            self._set(progress=96, message="Finishing up…")
            self._write_install_record(python)
            self._set_step("finish", "done")
            self._refresh_environment()
            elapsed = time.time() - started
            self._set(
                status="success",
                progress=100,
                message=f"Installed in {elapsed:.1f}s. Your calendar is ready.",
                launch_ready=True,
            )
            self._log("Installation complete. Your events stay on this device.")
            if options.launch:
                try:
                    self._launch()
                except Exception as exc:
                    self._log(f"Automatic launch failed: {exc}")
                    self._warning(
                        "Setup completed, but the app could not open automatically. "
                        "Use the Open Book My Date button."
                    )
        except Exception as exc:
            self._log("ERROR: " + str(exc))
            self._log(traceback.format_exc())
            with self._lock:
                for step in self._state["steps"]:
                    if step["status"] == "running":
                        step["status"] = "error"
                if not any(step["status"] == "error" for step in self._state["steps"]):
                    current = self._state.get("current_step")
                    for step in self._state["steps"]:
                        if step["key"] == current:
                            step["status"] = "error"
            self._set(status="error", error=str(exc), message="Setup could not finish.")

    # ---------------------------------------------------------------- install
    def _backup_database(self) -> None:
        database = self.data_dir / "book_my_date.db"
        if not database.exists():
            return
        backup_dir = self.data_dir / "backups"
        backup_dir.mkdir(parents=True, exist_ok=True)
        target = backup_dir / f"before-update-{datetime.now():%Y%m%d-%H%M%S}.db"
        try:
            source = sqlite3.connect(str(database))
            destination = sqlite3.connect(str(target))
            try:
                source.backup(destination)
            finally:
                destination.close()
                source.close()
            self._log(f"Backed up your existing calendar to {target.name}")
        except (OSError, sqlite3.Error) as exc:
            self._warning(f"Could not create a safety backup: {exc}")

    def _copy_application(self) -> None:
        self.app_dir.mkdir(parents=True, exist_ok=True)
        source = self.root / "book_my_date"
        destination = self.app_dir / "book_my_date"
        ignore = shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo", ".DS_Store")
        shutil.copytree(source, destination, dirs_exist_ok=True, ignore=ignore)
        for name in ("README.md", "LICENSE", "CHANGELOG.md"):
            origin = self.root / name
            if origin.exists():
                shutil.copy2(origin, self.app_dir / name)
        requirements = self.app_dir / "requirements.txt"
        requirements.write_text(REQUIREMENTS + "\n", encoding="utf-8")
        uninstaller = self.root / "uninstaller" / "uninstall.py"
        if uninstaller.exists():
            shutil.copy2(uninstaller, self.data_dir / "uninstall.py")
        (self.app_dir / "run.py").write_text(
            "import os\n"
            "from pathlib import Path\n\n"
            "os.environ.setdefault(\n"
            "    'BOOK_MY_DATE_HOME', str(Path(__file__).resolve().parent.parent)\n"
            ")\n\n"
            "from book_my_date.app import main\n\n"
            "if __name__ == '__main__':\n"
            "    raise SystemExit(main())\n",
            encoding="utf-8",
        )
        self._log(f"Copied application files to {self.app_dir}")

    def _ensure_venv(self) -> Path:
        python = _venv_python(self.venv_dir)
        if python.exists():
            try:
                check = subprocess.run(
                    [str(python), "-c", "import sys; print(sys.version_info[:2])"],
                    capture_output=True,
                    text=True,
                    timeout=20,
                )
                if check.returncode == 0:
                    self._log("Reusing the existing isolated environment")
                    return python
            except (OSError, subprocess.SubprocessError):
                pass
            self._log("Existing environment looks unhealthy; rebuilding it")
            shutil.rmtree(self.venv_dir, ignore_errors=True)

        self.venv_dir.parent.mkdir(parents=True, exist_ok=True)
        self._log("Creating a private virtual environment…")
        builder = venv.EnvBuilder(with_pip=True, clear=False, upgrade_deps=False)
        builder.create(self.venv_dir)
        python = _venv_python(self.venv_dir)
        if not python.exists():
            raise InstallError("Python could not create the virtual environment.")
        self._log("Virtual environment ready")
        return python

    def _pip(self, python: Path, args: list[str], *, allow_failure: bool = False) -> None:
        command = [
            str(python),
            "-m",
            "pip",
            "install",
            "--disable-pip-version-check",
            "--no-input",
            *args,
        ]
        self._log("Running: " + " ".join(shlex.quote(part) for part in command[1:]))
        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        env["PIP_NO_INPUT"] = "1"
        env["PIP_DISABLE_PIP_VERSION_CHECK"] = "1"
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
        process = subprocess.Popen(
            command,
            cwd=str(self.app_dir),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            env=env,
            creationflags=creationflags,
        )
        assert process.stdout is not None
        for line in process.stdout:
            self._log(line)
        code = process.wait()
        if code != 0 and not allow_failure:
            raise InstallError(
                "Dependency installation failed. Check your internet connection "
                "and try again."
            )

    def _install_dependencies(self, python: Path) -> None:
        self._pip(
            python,
            ["--upgrade", "pip", "setuptools", "wheel"],
            allow_failure=True,
        )
        self._log("Installing PySide6 (this can take a minute)…")
        self._set(progress=52)
        self._pip(python, ["--upgrade", "-r", str(self.app_dir / "requirements.txt")])
        self._set(progress=82, message="Verifying the installation…")
        check = subprocess.run(
            [str(python), "-c", "import PySide6; print(PySide6.__version__)"],
            cwd=str(self.app_dir),
            capture_output=True,
            text=True,
            timeout=60,
        )
        if check.returncode != 0:
            self._log(check.stdout or "")
            self._log(check.stderr or "")
            raise InstallError("PySide6 was installed but could not be loaded.")
        self._log(f"PySide6 {check.stdout.strip()} verified")

    def _create_shortcuts(self, python: Path) -> list[str]:
        try:
            if sys.platform == "win32":
                return self._create_windows_shortcuts(python)
            if sys.platform == "darwin":
                return self._create_macos_app(python)
            return self._create_linux_shortcuts(python)
        except Exception as exc:  # shortcuts are helpful, never fatal
            self._warning(f"Shortcut creation failed: {exc}")
            self._log(traceback.format_exc())
            return []

    def _linux_desktop_dir(self) -> Path | None:
        config = Path.home() / ".config" / "user-dirs.dirs"
        if config.exists():
            try:
                for line in config.read_text(encoding="utf-8").splitlines():
                    if line.startswith("XDG_DESKTOP_DIR="):
                        value = line.split("=", 1)[1].strip().strip('"')
                        value = value.replace("$HOME", str(Path.home()))
                        path = Path(value).expanduser()
                        if path.exists():
                            return path
            except OSError:
                pass
        default = Path.home() / "Desktop"
        return default if default.exists() else None

    def _create_linux_shortcuts(self, python: Path) -> list[str]:
        icon_dir = Path.home() / ".local" / "share" / "icons" / "hicolor" / "256x256" / "apps"
        icon_dir.mkdir(parents=True, exist_ok=True)
        icon = icon_dir / "book-my-date.png"
        shutil.copy2(self.root / "book_my_date" / "assets" / "app_icon_256.png", icon)

        apps_dir = Path.home() / ".local" / "share" / "applications"
        apps_dir.mkdir(parents=True, exist_ok=True)
        entry = (
            "[Desktop Entry]\n"
            "Version=1.0\n"
            "Type=Application\n"
            "Name=Book My Date\n"
            "GenericName=Calendar\n"
            "Comment=A beautiful local-first calendar and event booker\n"
            f"Exec={_desktop_quote(str(python))} "
            f"{_desktop_quote(str(self.app_dir / 'run.py'))}\n"
            f"Path={self.app_dir}\n"
            f"Icon={icon}\n"
            "Terminal=false\n"
            "Categories=Office;Calendar;\n"
            "StartupNotify=true\n"
            "StartupWMClass=book-my-date\n"
        )
        menu_file = apps_dir / "book-my-date.desktop"
        menu_file.write_text(entry, encoding="utf-8")
        menu_file.chmod(0o755)
        created = [str(menu_file)]

        setup_python = Path(sys.executable)
        uninstall_entry = (
            "[Desktop Entry]\n"
            "Version=1.0\n"
            "Type=Application\n"
            "Name=Uninstall Book My Date\n"
            "GenericName=Uninstaller\n"
            "Comment=Remove Book My Date from this computer\n"
            f"Exec={_desktop_quote(str(setup_python))} "
            f"{_desktop_quote(str(self.data_dir / 'uninstall.py'))} "
            "--all --purge --yes --force\n"
            f"Path={self.data_dir}\n"
            f"Icon={icon}\n"
            "Terminal=false\n"
            "Categories=Office;System;\n"
        )
        uninstall_menu = apps_dir / "book-my-date-uninstall.desktop"
        uninstall_menu.write_text(uninstall_entry, encoding="utf-8")
        uninstall_menu.chmod(0o755)
        created.append(str(uninstall_menu))

        desktop = self._linux_desktop_dir()
        if desktop is not None:
            desktop_file = desktop / "Book My Date.desktop"
            desktop_file.write_text(entry, encoding="utf-8")
            desktop_file.chmod(0o755)
            created.append(str(desktop_file))
            uninstall_desktop = desktop / "Uninstall Book My Date.desktop"
            uninstall_desktop.write_text(uninstall_entry, encoding="utf-8")
            uninstall_desktop.chmod(0o755)
            created.append(str(uninstall_desktop))

        bin_dir = Path.home() / ".local" / "bin"
        bin_dir.mkdir(parents=True, exist_ok=True)
        launcher = bin_dir / "book-my-date"
        launcher.write_text(
            "#!/bin/sh\n"
            f"cd {shlex.quote(str(self.app_dir))} || exit 1\n"
            f"exec {shlex.quote(str(python))} "
            f"{shlex.quote(str(self.app_dir / 'run.py'))} \"$@\"\n",
            encoding="utf-8",
        )
        launcher.chmod(0o755)
        created.append(str(launcher))
        if self._state["missing_libs"]:
            self._warning(
                "Some Qt system libraries appear to be missing. Use the setup "
                "page's library fix button before opening the app."
            )
        return created

    def _create_macos_app(self, python: Path) -> list[str]:
        applications = Path.home() / "Applications"
        applications.mkdir(parents=True, exist_ok=True)
        icon = self.root / "book_my_date" / "assets" / "app.icns"

        def write_bundle(
            bundle: Path,
            display_name: str,
            identifier: str,
            executable: str,
            command: str,
            working_dir: Path,
        ) -> None:
            if bundle.exists():
                shutil.rmtree(bundle)
            contents = bundle / "Contents"
            macos = contents / "MacOS"
            resources = contents / "Resources"
            macos.mkdir(parents=True)
            resources.mkdir(parents=True)
            (contents / "Info.plist").write_text(
                f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key><string>{display_name}</string>
  <key>CFBundleDisplayName</key><string>{display_name}</string>
  <key>CFBundleIdentifier</key><string>{identifier}</string>
  <key>CFBundleVersion</key><string>{APP_VERSION}</string>
  <key>CFBundleShortVersionString</key><string>{APP_VERSION}</string>
  <key>CFBundleExecutable</key><string>{executable}</string>
  <key>CFBundleIconFile</key><string>app.icns</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>LSMinimumSystemVersion</key><string>10.15</string>
  <key>NSHighResolutionCapable</key><true/>
  <key>LSApplicationCategoryType</key><string>public.app-category.productivity</string>
</dict>
</plist>
""",
                encoding="utf-8",
            )
            shutil.copy2(icon, resources / "app.icns")
            launcher = macos / executable
            launcher.write_text(
                "#!/bin/bash\n"
                f"cd {shlex.quote(str(working_dir))} || exit 1\n"
                f"exec {command} \"$@\"\n",
                encoding="utf-8",
            )
            launcher.chmod(0o755)

        bundle = applications / "Book My Date.app"
        write_bundle(
            bundle,
            "Book My Date",
            "io.bookmydate.app",
            "BookMyDate",
            f"{shlex.quote(str(python))} {shlex.quote(str(self.app_dir / 'run.py'))}",
            self.app_dir,
        )
        self._log(f"Created macOS app bundle at {bundle}")
        created = [str(bundle)]

        uninstall_bundle = applications / "Uninstall Book My Date.app"
        setup_python = Path(sys.executable)
        write_bundle(
            uninstall_bundle,
            "Uninstall Book My Date",
            "io.bookmydate.uninstall",
            "UninstallBookMyDate",
            f"{shlex.quote(str(setup_python))} "
            f"{shlex.quote(str(self.data_dir / 'uninstall.py'))} "
            "--all --purge --yes --force",
            self.data_dir,
        )
        created.append(str(uninstall_bundle))

        desktop = Path.home() / "Desktop"
        if desktop.exists():
            desktop_bundle = desktop / "Uninstall Book My Date.app"
            if desktop_bundle.exists():
                shutil.rmtree(desktop_bundle)
            shutil.copytree(uninstall_bundle, desktop_bundle)
            created.append(str(desktop_bundle))
        return created

    def _create_windows_shortcuts(self, python: Path) -> list[str]:
        pythonw = _venv_pythonw(self.venv_dir)
        setup_executable = Path(sys.executable)
        uninstall_python = setup_executable.with_name("pythonw.exe")
        if not uninstall_python.exists():
            uninstall_python = setup_executable
        icon = self.app_dir / "book_my_date" / "assets" / "app.ico"
        target = str(pythonw)
        arguments = f'"{self.app_dir / "run.py"}"'
        uninstall_arguments = (
            f'"{self.data_dir / "uninstall.py"}" --all --purge --yes --force'
        )
        working = str(self.app_dir)

        def quote(value: str) -> str:
            return value.replace("'", "''")

        script = (
            "$ErrorActionPreference = 'Stop'\n"
            "$ws = New-Object -ComObject WScript.Shell\n"
            "$targets = @([Environment]::GetFolderPath('Desktop'), "
            "[Environment]::GetFolderPath('Programs'))\n"
            "foreach ($dir in $targets) {\n"
            "  if (-not $dir) { continue }\n"
            "  $path = Join-Path $dir 'Book My Date.lnk'\n"
            "  $s = $ws.CreateShortcut($path)\n"
            f"  $s.TargetPath = '{quote(target)}'\n"
            f"  $s.Arguments = '{quote(arguments)}'\n"
            f"  $s.WorkingDirectory = '{quote(working)}'\n"
            f"  $s.IconLocation = '{quote(str(icon))},0'\n"
            "  $s.Description = 'Book My Date'\n"
            "  $s.Save()\n"
            "  Write-Output $path\n"
            "}\n"
            "foreach ($dir in $targets) {\n"
            "  if (-not $dir) { continue }\n"
            "  $path = Join-Path $dir 'Uninstall Book My Date.lnk'\n"
            "  $s = $ws.CreateShortcut($path)\n"
            f"  $s.TargetPath = '{quote(str(uninstall_python))}'\n"
            f"  $s.Arguments = '{quote(uninstall_arguments)}'\n"
            f"  $s.WorkingDirectory = '{quote(str(self.data_dir))}'\n"
            f"  $s.IconLocation = '{quote(str(icon))},0'\n"
            "  $s.Description = 'Uninstall Book My Date'\n"
            "  $s.Save()\n"
            "  Write-Output $path\n"
            "}\n"
        )
        encoded = base64.b64encode(script.encode("utf-16-le")).decode("ascii")
        result = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy",
                "Bypass",
                "-EncodedCommand",
                encoded,
            ],
            capture_output=True,
            text=True,
            timeout=60,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if result.returncode != 0:
            raise InstallError(result.stderr.strip() or "PowerShell could not create shortcuts.")
        created = [line.strip() for line in result.stdout.splitlines() if line.strip()]
        return created

    def _write_install_record(self, python: Path) -> None:
        record = {
            "version": APP_VERSION,
            "installed_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "app_dir": str(self.app_dir),
            "venv_python": str(python),
            "python": platform.python_version(),
            "platform": platform_label(),
            "source": str(self.root),
        }
        (self.data_dir / "install.json").write_text(
            json.dumps(record, indent=2) + "\n", encoding="utf-8"
        )
        self._log("Wrote installation record")

    # ----------------------------------------------------------------- public
    def launch(self) -> bool:
        try:
            self._launch()
            return True
        except Exception as exc:
            self._log(f"Could not launch the app: {exc}")
            with self._lock:
                self._state["error"] = str(exc)
            return False

    def _launch(self) -> None:
        if not self._state.get("launch_ready") and not (
            self.app_dir / "book_my_date"
        ).exists():
            raise InstallError("Book My Date is not installed yet.")
        python = _venv_pythonw(self.venv_dir)
        if not python.exists():
            python = _venv_python(self.venv_dir)
        if not python.exists():
            raise InstallError("The Python environment is missing. Run setup again.")
        env = os.environ.copy()
        env["BOOK_MY_DATE_HOME"] = str(self.data_dir)
        env.pop("PYTHONPATH", None)
        env.pop("PYTHONHOME", None)
        kwargs: dict[str, Any] = {
            "cwd": str(self.app_dir),
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
        subprocess.Popen([str(python), "-m", "book_my_date"], **kwargs)
        self._log("Book My Date launched")
        self._set(message="Book My Date is open. Enjoy your day.")

    def open_folder(self) -> None:
        path = self.data_dir
        path.mkdir(parents=True, exist_ok=True)
        try:
            if sys.platform == "win32":
                os.startfile(str(path))  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(path)])
            else:
                subprocess.Popen(["xdg-open", str(path)])
        except OSError as exc:
            self._warning(f"Could not open the data folder: {exc}")

    def fix_linux_libraries(self) -> bool:
        with self._lock:
            if self._state["libs_fixing"]:
                return False
            self._state["libs_fixing"] = True
            self._state["lib_error"] = ""
        thread = threading.Thread(target=self._fix_libs_worker, daemon=True)
        thread.start()
        return True

    def _fix_libs_worker(self) -> None:
        try:
            missing = detect_missing_linux_libs()
            if not missing:
                self._set(lib_error="Everything needed is already installed.")
                return
            if not shutil.which("apt-get"):
                raise InstallError(
                    "This automatic fix supports Ubuntu/Debian only. Install "
                    + ", ".join(missing)
                    + " with your system package manager."
                )
            if not shutil.which("pkexec"):
                raise InstallError(
                    "Administrator helper (pkexec) was not found. Install "
                    + ", ".join(missing)
                    + " from your app centre."
                )
            packages = " ".join(missing)
            command = [
                "pkexec",
                "sh",
                "-c",
                f"DEBIAN_FRONTEND=noninteractive apt-get update -qq && "
                f"DEBIAN_FRONTEND=noninteractive apt-get install -y {packages}",
            ]
            self._log("Requesting administrator permission to install: " + packages)
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            assert process.stdout is not None
            for line in process.stdout:
                self._log(line)
            code = process.wait(timeout=600)
            if code != 0:
                raise InstallError(
                    "The system library installation did not complete. You can "
                    "still install Book My Date and install the libraries later."
                )
            self._refresh_environment()
            if self._state["missing_libs"]:
                self._set(lib_error="Some libraries still appear to be missing.")
            else:
                self._log("All required system libraries are now available.")
        except Exception as exc:
            self._log(f"Library fix failed: {exc}")
            self._set(lib_error=str(exc))
        finally:
            self._set(libs_fixing=False)


@dataclass
class ServerContext:
    controller: Controller
    token: str
    started_at: float = field(default_factory=time.time)
    last_request: float = field(default_factory=time.time)


class WizardHandler(BaseHTTPRequestHandler):
    context: ServerContext

    def log_message(self, _format: str, *_args: Any) -> None:
        return

    # ------------------------------------------------------------------ helpers
    def _authorized(self, query: dict[str, list[str]]) -> bool:
        token = query.get("token", [""])[0]
        header = self.headers.get("X-Wizard-Token", "")
        return token == self.context.token or header == self.context.token

    def _send_json(self, payload: dict[str, Any], status: int = 200) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def _send_bytes(self, body: bytes, content_type: str, status: int = 200) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> dict[str, Any]:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = 0
        if length <= 0 or length > 64_000:
            return {}
        try:
            return json.loads(self.rfile.read(length).decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return {}

    # ---------------------------------------------------------------------- GET
    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)
        self.context.last_request = time.time()
        if parsed.path == "/":
            if not self._authorized(query):
                self._send_bytes(b"Setup link is invalid or expired.", "text/plain", 403)
                return
            try:
                template = (Path(__file__).with_name("wizard.html")).read_text(
                    encoding="utf-8"
                )
                body = (
                    template.replace("{{TOKEN}}", self.context.token)
                    .replace("{{VERSION}}", APP_VERSION)
                    .encode("utf-8")
                )
            except OSError:
                self._send_bytes(b"Wizard UI is missing.", "text/plain", 500)
                return
            self._send_bytes(body, "text/html; charset=utf-8")
            return
        if parsed.path in ("/logo.png", "/favicon.ico"):
            filename = (
                "app_icon_256.png" if parsed.path == "/logo.png" else "app.ico"
            )
            path = ROOT / "book_my_date" / "assets" / filename
            content_type = "image/png" if filename.endswith(".png") else "image/x-icon"
            try:
                self._send_bytes(path.read_bytes(), content_type)
            except OSError:
                self._send_bytes(b"", content_type, 404)
            return
        if parsed.path == "/api/status":
            if not self._authorized(query):
                self._send_json({"error": "unauthorized"}, 403)
                return
            self._send_json(self.context.controller.snapshot())
            return
        self._send_json({"error": "not found"}, 404)

    # --------------------------------------------------------------------- POST
    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)
        self.context.last_request = time.time()
        if not self._authorized(query):
            self._send_json({"error": "unauthorized"}, 403)
            return
        payload = self._read_json()
        controller = self.context.controller
        if parsed.path == "/api/install":
            options = InstallOptions(
                shortcuts=bool(payload.get("shortcuts", True)),
                launch=bool(payload.get("launch", True)),
            )
            if not controller.start(options):
                self._send_json({"ok": False, "error": "Setup is already running."}, 409)
                return
            self._send_json({"ok": True}, 202)
            return
        if parsed.path == "/api/launch":
            self._send_json({"ok": controller.launch()})
            return
        if parsed.path == "/api/open-folder":
            controller.open_folder()
            self._send_json({"ok": True})
            return
        if parsed.path == "/api/fix-libs":
            started = controller.fix_linux_libraries()
            self._send_json({"ok": started})
            return
        if parsed.path == "/api/close":
            self._send_json({"ok": True})
            threading.Timer(0.4, self.server.shutdown).start()  # type: ignore[attr-defined]
            return
        self._send_json({"error": "not found"}, 404)


def run_wizard(port: int = 0, open_browser: bool = True, timeout: int = 7200) -> int:
    controller = Controller()
    token = base64.urlsafe_b64encode(os.urandom(24)).decode("ascii").rstrip("=")
    context = ServerContext(controller=controller, token=token)
    handler = type("BoundWizardHandler", (WizardHandler,), {"context": context})
    server = ThreadingHTTPServer(("127.0.0.1", port), handler)
    server.daemon_threads = True
    actual_port = server.server_address[1]
    url = f"http://127.0.0.1:{actual_port}/?token={token}"

    print("Book My Date setup wizard")
    print(f"Open this link if your browser does not open automatically:\n{url}")
    if open_browser:
        threading.Timer(0.4, lambda: webbrowser.open(url, new=2)).start()

    def watchdog() -> None:
        while True:
            time.sleep(30)
            idle = time.time() - context.last_request
            if idle > timeout and controller.snapshot()["status"] != "running":
                print("Setup window timed out. Run the launcher again if needed.")
                server.shutdown()
                return

    threading.Thread(target=watchdog, daemon=True).start()
    try:
        server.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Book My Date setup wizard")
    parser.add_argument("--port", type=int, default=0, help="local port (default: auto)")
    parser.add_argument("--no-browser", action="store_true", help="do not open a browser")
    parser.add_argument(
        "--timeout",
        type=int,
        default=7200,
        help="close an idle wizard after this many seconds",
    )
    args = parser.parse_args(argv)
    return run_wizard(
        port=args.port,
        open_browser=not args.no_browser,
        timeout=max(300, args.timeout),
    )


if __name__ == "__main__":
    raise SystemExit(main())
