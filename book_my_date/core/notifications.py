"""Best-effort native desktop notifications without extra dependencies.

The in-app reminder toast is the primary, always-available surface.  This
module adds a native notification where the operating system supports one.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
import sys
from pathlib import Path

LOGGER = logging.getLogger(__name__)


def _escape_applescript(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def build_command(
    title: str,
    body: str,
    icon: str | Path | None = None,
    platform: str | None = None,
) -> list[str] | None:
    """Return the native notification command for a platform, if supported."""

    platform = platform or sys.platform
    if platform.startswith("linux"):
        if not shutil.which("notify-send"):
            return None
        command = ["notify-send", "--app-name", "Book My Date", "--urgency=normal"]
        if icon:
            command.extend(["--icon", str(icon)])
        command.extend([title, body])
        return command
    if platform == "darwin":
        script = (
            f'display notification "{_escape_applescript(body)}" '
            f'with title "{_escape_applescript(title)}"'
        )
        return ["osascript", "-e", script]
    return None


def notify(
    title: str,
    body: str,
    icon: str | Path | None = None,
    platform: str | None = None,
) -> bool:
    """Fire a native notification. Never raises and never blocks the UI."""

    command = build_command(title, body, icon=icon, platform=platform)
    if not command:
        return False
    try:
        subprocess.Popen(
            command,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        return True
    except (OSError, ValueError):
        LOGGER.debug("Native notification failed", exc_info=True)
        return False
