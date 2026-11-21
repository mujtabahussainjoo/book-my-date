from __future__ import annotations

import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import launcher
from uninstaller import uninstall


class UninstallerTests(unittest.TestCase):
    def test_install_root_matches_launcher(self) -> None:
        with tempfile.TemporaryDirectory() as temp, mock.patch.dict(
            os.environ, {"BOOK_MY_DATE_HOME": temp}
        ):
            self.assertEqual(uninstall.install_root(), launcher.install_root())

        with (
            mock.patch.dict(os.environ, {}, clear=True),
            mock.patch.object(Path, "home", return_value=Path("C:/Users/Test")),
            mock.patch.object(uninstall.sys, "platform", "win32"),
            mock.patch.object(launcher.sys, "platform", "win32"),
        ):
            self.assertEqual(uninstall.install_root(), launcher.install_root())

    def test_shortcut_paths_are_platform_specific(self) -> None:
        home = Path("C:/Users/Test")
        with (
            mock.patch.dict(os.environ, {}, clear=True),
            mock.patch.object(Path, "home", return_value=home),
        ):
            self.assertEqual(
                uninstall.shortcut_paths("win32"),
                [
                    home / "Desktop" / "Book My Date.lnk",
                    home
                    / "AppData"
                    / "Roaming"
                    / "Microsoft"
                    / "Windows"
                    / "Start Menu"
                    / "Programs"
                    / "Book My Date.lnk",
                    home / "Desktop" / "Uninstall Book My Date.lnk",
                    home
                    / "AppData"
                    / "Roaming"
                    / "Microsoft"
                    / "Windows"
                    / "Start Menu"
                    / "Programs"
                    / "Uninstall Book My Date.lnk",
                ],
            )
            self.assertEqual(
                uninstall.shortcut_paths("darwin"),
                [
                    home / "Applications" / "Book My Date.app",
                    home / "Applications" / "Uninstall Book My Date.app",
                    home / "Desktop" / "Uninstall Book My Date.app",
                ],
            )

    def test_shortcut_paths_linux_include_uninstall_icon(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp) / "home"
            (home / "Desktop").mkdir(parents=True)
            with mock.patch.object(Path, "home", return_value=home):
                paths = uninstall.shortcut_paths("linux")
            self.assertIn(
                home / ".local/share/applications/book-my-date-uninstall.desktop",
                paths,
            )
            self.assertIn(home / "Desktop" / "Uninstall Book My Date.desktop", paths)

    def test_candidate_roots_include_override_and_default(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp) / "home"
            override = Path(temp) / "custom"
            with (
                mock.patch.object(Path, "home", return_value=home),
                mock.patch.dict(
                    os.environ,
                    {"XDG_DATA_HOME": str(home / ".local" / "share")},
                    clear=True,
                ),
            ):
                roots = uninstall.candidate_roots("linux", str(override))
            self.assertEqual(roots[0], override)
            self.assertIn(home / ".local" / "share" / "book-my-date", roots)

    def test_main_all_removes_every_standard_root(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp) / "home"
            xdg_root = home / "xdg" / "book-my-date"
            default_root = home / ".local" / "share" / "book-my-date"
            for root in (xdg_root, default_root):
                root.mkdir(parents=True)
                (root / "install.json").write_text("{}", encoding="utf-8")
            (xdg_root / "book_my_date.db").write_text("events", encoding="utf-8")

            with (
                mock.patch.object(Path, "home", return_value=home),
                mock.patch.object(uninstall.sys, "platform", "linux"),
                mock.patch.dict(
                    os.environ, {"XDG_DATA_HOME": str(home / "xdg")}, clear=True
                ),
                mock.patch.object(uninstall, "running_pids", return_value=[]),
                contextlib.redirect_stdout(io.StringIO()),
            ):
                code = uninstall.main(
                    ["--all", "--purge", "--yes", "--no-shortcuts"]
                )

            self.assertEqual(code, 0)
            self.assertFalse(xdg_root.exists())
            self.assertFalse(default_root.exists())

    def test_build_plan_keeps_calendar_data_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp) / "home"
            root = Path(temp) / "data"
            (root / "app" / "book_my_date").mkdir(parents=True)
            (root / "venv").mkdir()
            (root / "install.json").write_text("{}", encoding="utf-8")
            database = root / "book_my_date.db"
            database.write_text("events", encoding="utf-8")

            with mock.patch.object(Path, "home", return_value=home):
                plan = uninstall.build_plan(
                    root,
                    platform_name="linux",
                    record={},
                )

            self.assertIn(root / "app", plan.directories)
            self.assertIn(root / "venv", plan.directories)
            self.assertIn(root / "install.json", plan.files)
            self.assertNotIn(database, plan.files)
            self.assertFalse(plan.purge_data)

    def test_build_plan_purge_includes_database_and_settings(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp) / "home"
            root = Path(temp) / "data"
            root.mkdir()

            with mock.patch.object(Path, "home", return_value=home):
                plan = uninstall.build_plan(
                    root,
                    purge_data=True,
                    platform_name="linux",
                    record={},
                )

            self.assertIn(root / "book_my_date.db", plan.files)
            self.assertIn(root / "backups", plan.directories)
            self.assertIn(
                home / ".config" / "BookMyDate" / "BookMyDate.conf", plan.files
            )
            self.assertTrue(plan.purge_data)

    def test_build_plan_skips_app_folder_outside_install_root(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            root = base / "data"
            root.mkdir()
            outside = base / "elsewhere"
            outside.mkdir()

            with mock.patch.object(Path, "home", return_value=base / "home"):
                plan = uninstall.build_plan(
                    root,
                    platform_name="linux",
                    record={"app_dir": str(outside)},
                )

            self.assertNotIn(outside, plan.directories)
            self.assertTrue(any("outside" in warning for warning in plan.warnings))

    def test_execute_removes_app_but_keeps_database(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "data"
            (root / "app" / "book_my_date").mkdir(parents=True)
            (root / "app" / "book_my_date" / "__main__.py").write_text("", encoding="utf-8")
            (root / "venv").mkdir()
            (root / "venv" / "pyvenv.cfg").write_text("", encoding="utf-8")
            (root / "install.json").write_text(json.dumps({}), encoding="utf-8")
            database = root / "book_my_date.db"
            database.write_text("events", encoding="utf-8")

            plan = uninstall.build_plan(
                root,
                remove_shortcuts=False,
                platform_name="linux",
                record={},
            )
            actions, errors = uninstall.execute(plan)

            self.assertEqual(errors, [])
            self.assertTrue(actions)
            self.assertFalse((root / "app").exists())
            self.assertFalse((root / "venv").exists())
            self.assertFalse((root / "install.json").exists())
            self.assertTrue(database.exists())

    def test_execute_purge_removes_root_when_empty(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "data"
            (root / "backups").mkdir(parents=True)
            (root / "book_my_date.db").write_text("events", encoding="utf-8")
            (root / "install.json").write_text("{}", encoding="utf-8")

            plan = uninstall.build_plan(
                root,
                purge_data=True,
                remove_shortcuts=False,
                platform_name="linux",
                record={},
            )
            actions, errors = uninstall.execute(plan)

            self.assertEqual(errors, [])
            self.assertFalse(root.exists())
            self.assertTrue(any(str(root) in action for action in actions))

    def test_dry_run_leaves_files_in_place(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "data"
            (root / "app").mkdir(parents=True)
            (root / "install.json").write_text("{}", encoding="utf-8")

            plan = uninstall.build_plan(
                root,
                remove_shortcuts=False,
                platform_name="linux",
                record={},
            )
            actions, errors = uninstall.execute(plan, dry_run=True)

            self.assertEqual(errors, [])
            self.assertTrue(actions)
            self.assertTrue((root / "app").is_dir())
            self.assertTrue((root / "install.json").is_file())

    def test_main_purge_confirmed_removes_everything(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "data"
            root.mkdir()
            (root / "book_my_date.db").write_text("events", encoding="utf-8")

            with (
                mock.patch.object(uninstall, "running_pids", return_value=[]),
                contextlib.redirect_stdout(io.StringIO()),
            ):
                code = uninstall.main(
                    [
                        "--data-dir",
                        str(root),
                        "--purge",
                        "--yes",
                        "--no-shortcuts",
                    ]
                )

            self.assertEqual(code, 0)
            self.assertFalse(root.exists())

    def test_main_refuses_to_uninstall_while_app_is_running(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "data"
            root.mkdir(parents=True)
            (root / "install.json").write_text("{}", encoding="utf-8")

            with (
                mock.patch.object(uninstall, "running_pids", return_value=[4242]),
                contextlib.redirect_stdout(io.StringIO()),
            ):
                code = uninstall.main(
                    ["--data-dir", str(root), "--yes", "--no-shortcuts"]
                )

            self.assertEqual(code, 1)
            self.assertTrue((root / "install.json").is_file())


if __name__ == "__main__":
    unittest.main()
