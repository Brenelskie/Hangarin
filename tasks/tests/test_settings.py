import json
import os
import subprocess
import sys
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase


BASE_DIR = Path(__file__).resolve().parents[2]


class DevelopmentSettingsTests(SimpleTestCase):
    def test_development_defaults_are_safe_and_complete(self):
        self.assertEqual(settings.TIME_ZONE, "Asia/Manila")
        self.assertIn("tasks", settings.INSTALLED_APPS)
        self.assertEqual(settings.STATIC_ROOT, BASE_DIR / "staticfiles")
        self.assertIn(BASE_DIR / "templates", settings.TEMPLATES[0]["DIRS"])
        self.assertEqual(settings.LOGIN_URL, "login")

    def test_generated_and_secret_files_are_ignored(self):
        ignored = (BASE_DIR / ".gitignore").read_text(encoding="utf-8")
        for entry in (".venv/", ".env", "*.sqlite3", "staticfiles/"):
            with self.subTest(entry=entry):
                self.assertIn(entry, ignored)


class ProductionSettingsTests(SimpleTestCase):
    @staticmethod
    def load_settings(**values):
        environment = os.environ.copy()
        for key in (
            "DJANGO_SECRET_KEY",
            "DJANGO_ALLOWED_HOSTS",
            "DJANGO_CSRF_TRUSTED_ORIGINS",
            "DJANGO_DEBUG",
        ):
            environment.pop(key, None)
        environment.update({"DJANGO_ENV": "production", **values})
        script = """
import json
from django.conf import settings

print(json.dumps({
    "debug": settings.DEBUG,
    "allowed_hosts": settings.ALLOWED_HOSTS,
    "trusted_origins": settings.CSRF_TRUSTED_ORIGINS,
    "secure_session": settings.SESSION_COOKIE_SECURE,
    "secure_csrf": settings.CSRF_COOKIE_SECURE,
    "ssl_redirect": settings.SECURE_SSL_REDIRECT,
}))
"""
        return subprocess.run(
            [sys.executable, "-c", script],
            cwd=BASE_DIR,
            env={**environment, "DJANGO_SETTINGS_MODULE": "hangarin.settings"},
            capture_output=True,
            text=True,
            check=False,
        )

    def test_production_rejects_a_missing_secret(self):
        result = self.load_settings(
            DJANGO_ALLOWED_HOSTS="hangarin.example.com",
            DJANGO_CSRF_TRUSTED_ORIGINS="https://hangarin.example.com",
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("DJANGO_SECRET_KEY", result.stderr)

    def test_production_accepts_explicit_host_and_origin(self):
        result = self.load_settings(
            DJANGO_SECRET_KEY="a-production-secret-key-longer-than-fifty-characters-123456789",
            DJANGO_ALLOWED_HOSTS="hangarin.example.com",
            DJANGO_CSRF_TRUSTED_ORIGINS="https://hangarin.example.com",
            DJANGO_DEBUG="False",
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        configured = json.loads(result.stdout)
        self.assertFalse(configured["debug"])
        self.assertEqual(configured["allowed_hosts"], ["hangarin.example.com"])
        self.assertEqual(
            configured["trusted_origins"], ["https://hangarin.example.com"]
        )
        self.assertTrue(configured["secure_session"])
        self.assertTrue(configured["secure_csrf"])
        self.assertTrue(configured["ssl_redirect"])
