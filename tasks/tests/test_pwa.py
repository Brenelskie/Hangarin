import json
import struct
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import TestCase


BASE_DIR = Path(__file__).resolve().parents[2]


class ProgressiveWebAppTests(TestCase):
    def test_manifest_describes_installable_hangarin_with_real_png_icons(self):
        response = self.client.get("/manifest.json")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response["Content-Type"].startswith("application/json"))
        manifest = json.loads(response.content)
        self.assertEqual(manifest["name"], "Hangarin")
        self.assertEqual(manifest["display"], "standalone")
        self.assertEqual(manifest["start_url"], "/")
        self.assertEqual(manifest["scope"], "/")
        self.assertEqual(manifest["theme_color"], "#0b1f33")

        for size in (192, 512):
            with self.subTest(size=size):
                icon = next(
                    icon for icon in manifest["icons"]
                    if icon["sizes"] == f"{size}x{size}"
                )
                self.assertEqual(icon["type"], "image/png")
                self.assertEqual(icon["src"], f"/static/tasks/img/icon-{size}.png")
                data = (BASE_DIR / icon["src"].lstrip("/")).read_bytes()
                self.assertEqual(data[:8], b"\x89PNG\r\n\x1a\n")
                self.assertEqual(struct.unpack(">II", data[16:24]), (size, size))

    def test_login_and_authenticated_pages_register_service_worker(self):
        for path in ("/accounts/login/", "/"):
            with self.subTest(path=path):
                if path == "/":
                    user = get_user_model().objects.create_user(
                        username="pwa-user", password="pwa-password"
                    )
                    self.client.force_login(user)
                response = self.client.get(path)
                self.assertContains(response, 'rel="manifest" href="/manifest.json"')
                self.assertContains(response, "navigator.serviceWorker.register('/serviceworker.js'")

    def test_service_worker_and_public_offline_page_are_served(self):
        response = self.client.get("/serviceworker.js")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response["Content-Type"].startswith("application/javascript"))
        self.assertIn(b"self.addEventListener('fetch'", response.content)

        offline = self.client.get("/offline/")
        self.assertContains(offline, "You are offline")
        self.assertContains(offline, "Reconnect to see your tasks")
