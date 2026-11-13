from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from book_my_date import config


class ConfigTests(unittest.TestCase):
    def test_home_override_controls_all_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            with mock.patch.dict(os.environ, {"BOOK_MY_DATE_HOME": temp}):
                root = Path(temp)
                self.assertEqual(config.app_data_dir(), root)
                self.assertEqual(config.db_path(), root / config.DB_FILENAME)
                self.assertEqual(config.log_path(), root / config.LOG_FILENAME)
                created = config.ensure_app_dirs()
                self.assertEqual(created, root)
                self.assertTrue(root.is_dir())

    def test_windows_data_dir_uses_profile_not_store_appdata(self) -> None:
        with (
            mock.patch.dict(os.environ, {}, clear=True),
            mock.patch.object(config.sys, "platform", "win32"),
            mock.patch.object(config.Path, "home", return_value=Path("C:/Users/Test")),
        ):
            self.assertEqual(
                config.app_data_dir(), Path("C:/Users/Test") / "BookMyDate"
            )

    def test_bundled_assets_exist(self) -> None:
        for name in (
            "app_icon.png",
            "app_icon_256.png",
            "app.ico",
            "app.icns",
            "logo.svg",
        ):
            path = config.asset_path(name)
            self.assertTrue(path.exists(), name)
            self.assertGreater(path.stat().st_size, 0, name)

    def test_metadata(self) -> None:
        self.assertEqual(config.APP_NAME, "Book My Date")
        self.assertEqual(config.APP_ID, "io.bookmydate.app")
        self.assertRegex(config.VERSION, r"^\d+\.\d+\.\d+$")


if __name__ == "__main__":
    unittest.main()
