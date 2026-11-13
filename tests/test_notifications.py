from __future__ import annotations

import unittest
from unittest import mock

from book_my_date.core import notifications


class NotificationTests(unittest.TestCase):
    def test_linux_command_with_icon(self) -> None:
        with mock.patch("shutil.which", return_value="/usr/bin/notify-send"):
            command = notifications.build_command(
                "Reminder", "Standup at 09:00", icon="/tmp/icon.png", platform="linux"
            )
        self.assertEqual(
            command,
            [
                "notify-send",
                "--app-name",
                "Book My Date",
                "--urgency=normal",
                "--icon",
                "/tmp/icon.png",
                "Reminder",
                "Standup at 09:00",
            ],
        )

    def test_linux_without_notify_send(self) -> None:
        with mock.patch("shutil.which", return_value=None):
            self.assertIsNone(
                notifications.build_command("Title", "Body", platform="linux")
            )

    def test_macos_command_escapes_applescript(self) -> None:
        command = notifications.build_command(
            'Say "hello"', 'Line "one"\nLine two', platform="darwin"
        )
        self.assertEqual(command[0], "osascript")
        self.assertIn('\\"hello\\"', command[2])
        self.assertIn("Line two", command[2])

    def test_unsupported_platform(self) -> None:
        self.assertIsNone(
            notifications.build_command("Title", "Body", platform="win32")
        )

    def test_notify_never_raises(self) -> None:
        with mock.patch(
            "book_my_date.core.notifications.build_command",
            return_value=["/missing/command", "x"],
        ), mock.patch("subprocess.Popen", side_effect=OSError("no binary")):
            self.assertFalse(notifications.notify("Title", "Body"))

    def test_notify_returns_true_after_spawn(self) -> None:
        with mock.patch(
            "book_my_date.core.notifications.build_command",
            return_value=["notify-send", "Title", "Body"],
        ), mock.patch("subprocess.Popen") as popen:
            self.assertTrue(notifications.notify("Title", "Body"))
        popen.assert_called_once()


if __name__ == "__main__":
    unittest.main()
