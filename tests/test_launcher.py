from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import launcher


class LauncherTests(unittest.TestCase):
    def test_install_root_honours_override(self) -> None:
        with tempfile.TemporaryDirectory() as temp, mock.patch.dict(
            os.environ, {"BOOK_MY_DATE_HOME": temp}
        ):
            self.assertEqual(launcher.install_root(), Path(temp))

    def test_windows_install_root_uses_profile(self) -> None:
        with (
            mock.patch.dict(os.environ, {}, clear=True),
            mock.patch.object(launcher.sys, "platform", "win32"),
            mock.patch.object(launcher.Path, "home", return_value=Path("C:/Users/Test")),
        ):
            self.assertEqual(
                launcher.install_root(), Path("C:/Users/Test") / "BookMyDate"
            )

    def test_is_installed_requires_record_app_and_python(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.assertFalse(launcher._is_installed(root))

            app_dir = root / "app"
            (app_dir / "book_my_date").mkdir(parents=True)
            (app_dir / "book_my_date" / "__main__.py").write_text("", encoding="utf-8")
            python = launcher._venv_python(root)
            python.parent.mkdir(parents=True)
            python.write_text("", encoding="utf-8")
            (root / "install.json").write_text(
                json.dumps({"version": "1.0.0", "app_dir": str(app_dir)}),
                encoding="utf-8",
            )
            self.assertTrue(launcher._is_installed(root))

    def test_is_installed_false_for_bad_record(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "install.json").write_text("{not json", encoding="utf-8")
            self.assertFalse(launcher._is_installed(root))

    def test_install_record_falls_back_to_empty(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            self.assertEqual(launcher._install_record(Path(temp)), {})

    def test_uninstall_flag_delegates_with_total_flags(self) -> None:
        with mock.patch.object(launcher.subprocess, "call", return_value=0) as call:
            code = launcher.main(["--uninstall"])
        command = call.call_args.args[0]
        self.assertEqual(code, 0)
        self.assertEqual(Path(command[1]), launcher.UNINSTALLER)
        self.assertTrue(
            {"--all", "--purge", "--yes", "--force"}.issubset(set(command))
        )


if __name__ == "__main__":
    unittest.main()
