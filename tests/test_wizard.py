from __future__ import annotations

import json
import os
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest import mock
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from installer import wizard


class WizardHttpTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.env_patch = mock.patch.dict(
            os.environ, {"BOOK_MY_DATE_HOME": str(self.root)}
        )
        self.env_patch.start()

        self.controller = wizard.Controller()
        self.token = "test-token-123"
        context = wizard.ServerContext(controller=self.controller, token=self.token)
        handler = type("TestWizardHandler", (wizard.WizardHandler,), {"context": context})
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self.server.daemon_threads = True
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_address[1]}"

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=3)
        self.env_patch.stop()
        self.temp_dir.cleanup()

    def get(self, path: str, token: str | None = "default") -> tuple[int, bytes, str]:
        if token == "default":
            token = self.token
        separator = "&" if "?" in path else "?"
        url = self.base + path + (f"{separator}token={token}" if token else "")
        with urlopen(url, timeout=5) as response:
            return response.status, response.read(), response.headers.get_content_type()

    def test_status_endpoint(self) -> None:
        status, body, content_type = self.get("/api/status")
        self.assertEqual(status, 200)
        self.assertEqual(content_type, "application/json")
        payload = json.loads(body)
        self.assertEqual(payload["status"], "idle")
        self.assertEqual(payload["version"], wizard.APP_VERSION)
        self.assertEqual(payload["data_dir"], str(self.root))
        self.assertEqual(len(payload["steps"]), 5)
        self.assertTrue(payload["python_ok"])

    def test_page_renders_token_and_version(self) -> None:
        status, body, content_type = self.get("/")
        self.assertEqual(status, 200)
        self.assertEqual(content_type, "text/html")
        text = body.decode("utf-8")
        self.assertIn(self.token, text)
        self.assertIn(wizard.APP_VERSION, text)
        self.assertNotIn("{{TOKEN}}", text)
        self.assertNotIn("{{VERSION}}", text)
        self.assertIn("Book My Date", text)

    def test_logo_is_served(self) -> None:
        status, body, content_type = self.get("/logo.png", token=None)
        self.assertEqual(status, 200)
        self.assertEqual(content_type, "image/png")
        self.assertTrue(body.startswith(b"\x89PNG"))

    def test_unauthorized_requests_are_rejected(self) -> None:
        with self.assertRaises(HTTPError) as raised:
            self.get("/api/status", token="wrong")
        self.assertEqual(raised.exception.code, 403)
        with self.assertRaises(HTTPError) as raised:
            self.get("/", token="")
        self.assertEqual(raised.exception.code, 403)

    def test_post_unknown_endpoint_returns_404(self) -> None:
        request = Request(
            self.base + "/api/unknown?token=" + self.token,
            data=b"{}",
            headers={"X-Wizard-Token": self.token, "Content-Type": "application/json"},
            method="POST",
        )
        with self.assertRaises(HTTPError) as raised:
            urlopen(request, timeout=5)
        self.assertEqual(raised.exception.code, 404)



class WizardHelperTests(unittest.TestCase):
    def test_read_version_matches_package(self) -> None:
        from book_my_date.config import VERSION

        self.assertEqual(wizard.read_version(), VERSION)

    def test_html_file_exists_with_placeholders(self) -> None:
        text = Path(wizard.__file__).with_name("wizard.html").read_text(encoding="utf-8")
        self.assertIn("{{TOKEN}}", text)
        self.assertIn("{{VERSION}}", text)
        self.assertIn("/api/install", text)
        self.assertIn("/api/status", text)

    def test_windows_install_root_uses_profile(self) -> None:
        with (
            mock.patch.dict(os.environ, {}, clear=True),
            mock.patch.object(wizard.sys, "platform", "win32"),
            mock.patch.object(wizard.Path, "home", return_value=Path("C:/Users/Test")),
        ):
            self.assertEqual(
                wizard.install_root(), Path("C:/Users/Test") / "BookMyDate"
            )

    def test_installed_runner_pins_its_data_home(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with mock.patch.dict(os.environ, {"BOOK_MY_DATE_HOME": str(root)}):
                controller = wizard.Controller()
                controller._copy_application()
            runner = (root / "app" / "run.py").read_text(encoding="utf-8")
            self.assertIn("BOOK_MY_DATE_HOME", runner)
            self.assertIn("parent.parent", runner)

    def test_install_options_defaults(self) -> None:
        options = wizard.InstallOptions()
        self.assertTrue(options.shortcuts)
        self.assertTrue(options.launch)


if __name__ == "__main__":
    unittest.main()
