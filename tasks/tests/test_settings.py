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
        self.assertEqual(settings.LOGIN_URL, "account_login")
        self.assertIn("allauth.account", settings.INSTALLED_APPS)
        self.assertIn("allauth.socialaccount", settings.INSTALLED_APPS)
        self.assertFalse(settings.ACCOUNT_LOGOUT_ON_GET)
        self.assertFalse(settings.SOCIALACCOUNT_LOGIN_ON_GET)
        self.assertFalse(settings.SOCIALACCOUNT_STORE_TOKENS)
        self.assertFalse(settings.SOCIALACCOUNT_EMAIL_AUTHENTICATION)

    def test_generated_and_secret_files_are_ignored(self):
        ignored = (BASE_DIR / ".gitignore").read_text(encoding="utf-8")
        for entry in (".venv/", ".env", "*.sqlite3", "staticfiles/"):
            with self.subTest(entry=entry):
                self.assertIn(entry, ignored)

    def test_environment_example_documents_every_deployment_control(self):
        example = (BASE_DIR / ".env.example").read_text(encoding="utf-8")
        for setting_name in (
            "DJANGO_ENV",
            "DJANGO_SECRET_KEY",
            "DJANGO_DEBUG",
            "DJANGO_ALLOWED_HOSTS",
            "DJANGO_CSRF_TRUSTED_ORIGINS",
            "DJANGO_ENABLE_HSTS",
            "HANGARIN_ALLOW_PRODUCTION_SEED",
            "GOOGLE_OAUTH_CLIENT_ID",
            "GOOGLE_OAUTH_CLIENT_SECRET",
            "GITHUB_OAUTH_CLIENT_ID",
            "GITHUB_OAUTH_CLIENT_SECRET",
        ):
            with self.subTest(setting_name=setting_name):
                self.assertIn(f"{setting_name}=", example)

    def test_readme_covers_beginner_setup_and_release_recovery(self):
        readme = (BASE_DIR / "README.md").read_text(encoding="utf-8")
        for instruction in (
            "py -3.13 -m venv .venv",
            "python manage.py migrate",
            "python manage.py create_initial_data",
            "python manage.py test",
            "Manual configuration",
            "/static/",
            "Hosted smoke test",
            "Backup before an update",
            "Rollback",
            "python manage.py createsuperuser",
            "/accounts/google/login/callback/",
            "/accounts/github/login/callback/",
            "regular user",
        ):
            with self.subTest(instruction=instruction):
                self.assertIn(instruction, readme)
        self.assertNotIn("/home/qtaqua", readme)
        self.assertNotIn("Hangrin", readme)


class ProductionSettingsTests(SimpleTestCase):
    production_secret = (
        "4c#9!vP7@xQ2$Lm8&bN5*Zd3^sK6-wR1+fT0=Hy9%Ua4?Cg7!eV2"
    )

    @staticmethod
    def production_environment(**values):
        environment = os.environ.copy()
        environment.update(
            {
                "DJANGO_ENV": "production",
                "DJANGO_SECRET_KEY": "",
                "DJANGO_DEBUG": "False",
                "DJANGO_ALLOWED_HOSTS": "",
                "DJANGO_CSRF_TRUSTED_ORIGINS": "",
                "DJANGO_ENABLE_HSTS": "False",
                "HANGARIN_ALLOW_PRODUCTION_SEED": "False",
                "GOOGLE_OAUTH_CLIENT_ID": "",
                "GOOGLE_OAUTH_CLIENT_SECRET": "",
                "GITHUB_OAUTH_CLIENT_ID": "",
                "GITHUB_OAUTH_CLIENT_SECRET": "",
                **values,
            }
        )
        return environment

    @classmethod
    def load_settings(cls, **values):
        environment = cls.production_environment(**values)
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
    "mail_backend": settings.MAILERS["default"]["BACKEND"],
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

    @classmethod
    def run_deployment_check(cls):
        environment = cls.production_environment(
            DJANGO_SECRET_KEY=cls.production_secret,
            DJANGO_ALLOWED_HOSTS="hangarin.example.com",
            DJANGO_CSRF_TRUSTED_ORIGINS="https://hangarin.example.com",
            DJANGO_DEBUG="False",
            DJANGO_ENABLE_HSTS="True",
            GOOGLE_OAUTH_CLIENT_ID="test-google-client-id",
            GOOGLE_OAUTH_CLIENT_SECRET="test-google-client-secret",
            GITHUB_OAUTH_CLIENT_ID="test-github-client-id",
            GITHUB_OAUTH_CLIENT_SECRET="test-github-client-secret",
        )
        return subprocess.run(
            [
                sys.executable,
                "manage.py",
                "check",
                "--deploy",
                "--fail-level",
                "WARNING",
            ],
            cwd=BASE_DIR,
            env=environment,
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
            DJANGO_SECRET_KEY=self.production_secret,
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
        self.assertEqual(
            configured["mail_backend"],
            "django.core.mail.backends.smtp.EmailBackend",
        )

    def test_production_accepts_leading_dot_subdomain_host_pattern(self):
        result = self.load_settings(
            DJANGO_SECRET_KEY=self.production_secret,
            DJANGO_ALLOWED_HOSTS=".example.com",
            DJANGO_CSRF_TRUSTED_ORIGINS="https://hangarin.example.com",
        )

        self.assertEqual(result.returncode, 0, result.stderr)

    def test_production_rejects_wildcard_allowed_host(self):
        result = self.load_settings(
            DJANGO_SECRET_KEY=self.production_secret,
            DJANGO_ALLOWED_HOSTS="*",
            DJANGO_CSRF_TRUSTED_ORIGINS="https://hangarin.example.com",
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("DJANGO_ALLOWED_HOSTS", result.stderr)

    def test_production_rejects_scheme_bearing_allowed_host(self):
        result = self.load_settings(
            DJANGO_SECRET_KEY=self.production_secret,
            DJANGO_ALLOWED_HOSTS="https://hangarin.example.com",
            DJANGO_CSRF_TRUSTED_ORIGINS="https://hangarin.example.com",
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("DJANGO_ALLOWED_HOSTS", result.stderr)

    def test_production_rejects_http_csrf_origin(self):
        result = self.load_settings(
            DJANGO_SECRET_KEY=self.production_secret,
            DJANGO_ALLOWED_HOSTS="hangarin.example.com",
            DJANGO_CSRF_TRUSTED_ORIGINS="http://hangarin.example.com",
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("DJANGO_CSRF_TRUSTED_ORIGINS", result.stderr)

    def test_production_rejects_csrf_origin_host_mismatch(self):
        result = self.load_settings(
            DJANGO_SECRET_KEY=self.production_secret,
            DJANGO_ALLOWED_HOSTS="hangarin.example.com",
            DJANGO_CSRF_TRUSTED_ORIGINS="https://other.example.com",
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("DJANGO_CSRF_TRUSTED_ORIGINS", result.stderr)

    def test_production_rejects_missing_host_or_origin(self):
        scenarios = (
            (
                {"DJANGO_CSRF_TRUSTED_ORIGINS": "https://hangarin.example.com"},
                "DJANGO_ALLOWED_HOSTS",
            ),
            (
                {"DJANGO_ALLOWED_HOSTS": "hangarin.example.com"},
                "DJANGO_CSRF_TRUSTED_ORIGINS",
            ),
        )
        for values, setting_name in scenarios:
            with self.subTest(setting_name=setting_name):
                result = self.load_settings(
                    DJANGO_SECRET_KEY=self.production_secret,
                    **values,
                )
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(setting_name, result.stderr)

    def test_django_deployment_checks_accept_complete_secure_configuration(self):
        result = self.run_deployment_check()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("System check identified no issues", result.stdout)
