import json
import os
import subprocess
import sys
from pathlib import Path

from allauth.core import context
from allauth.socialaccount.adapter import get_adapter
from allauth.socialaccount.models import SocialAccount, SocialApp, SocialLogin
from allauth.socialaccount.providers.google.provider import GoogleProvider
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.sessions.middleware import SessionMiddleware
from django.http import HttpResponse
from django.test import Client, RequestFactory, TestCase, override_settings
from django.urls import reverse

from hangarin.account_adapters import (
    HangarinAccountAdapter,
    HangarinSocialAccountAdapter,
)


BASE_DIR = Path(__file__).resolve().parents[2]


def request_with_session(path="/"):
    request = RequestFactory().get(path)
    SessionMiddleware(lambda req: None).process_request(request)
    request.session.save()
    return request


def csrf_failure_for_test(request, reason=""):
    return HttpResponse(status=403)


class LocalRegistrationTests(TestCase):
    def test_valid_signup_creates_and_logs_in_regular_user(self):
        response = self.client.post(
            reverse("account_signup"),
            {
                "username": "new-student",
                "password1": "A-safe-study-password-42",
                "password2": "A-safe-study-password-42",
            },
        )

        user = get_user_model().objects.get(username="new-student")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("dashboard"))
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertEqual(int(self.client.session["_auth_user_id"]), user.pk)

    def test_duplicate_username_is_rejected(self):
        get_user_model().objects.create_user("taken", password="Existing-pass-42")

        response = self.client.post(
            reverse("account_signup"),
            {
                "username": "taken",
                "password1": "Another-safe-password-42",
                "password2": "Another-safe-password-42",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(get_user_model().objects.filter(username="taken").count(), 1)

    def test_weak_or_mismatched_password_is_rejected(self):
        payloads = (
            {
                "username": "weak-user",
                "password1": "password",
                "password2": "password",
            },
            {
                "username": "mismatch-user",
                "password1": "A-safe-study-password-42",
                "password2": "Different-safe-password-42",
            },
        )

        for payload in payloads:
            with self.subTest(username=payload["username"]):
                response = self.client.post(reverse("account_signup"), payload)
                self.assertEqual(response.status_code, 200)
                self.assertFalse(
                    get_user_model().objects.filter(
                        username=payload["username"]
                    ).exists()
                )

    def test_unexpected_privilege_fields_are_ignored(self):
        response = self.client.post(
            reverse("account_signup"),
            {
                "username": "regular-only",
                "password1": "A-safe-study-password-42",
                "password2": "A-safe-study-password-42",
                "is_staff": "on",
                "is_superuser": "on",
            },
        )

        user = get_user_model().objects.get(username="regular-only")
        self.assertEqual(response.status_code, 302)
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)


class PrivilegeAdapterTests(TestCase):
    def test_local_adapter_clears_preexisting_privilege_flags(self):
        class SignupData:
            cleaned_data = {
                "username": "adapter-user",
                "password1": "A-safe-study-password-42",
            }

        user = get_user_model()(is_staff=True, is_superuser=True)

        saved = HangarinAccountAdapter().save_user(
            request_with_session(), user, SignupData()
        )

        self.assertFalse(saved.is_staff)
        self.assertFalse(saved.is_superuser)

    def test_social_adapter_creates_regular_user_and_repeat_identity_resolves_it(self):
        request = request_with_session()
        provider = GoogleProvider(
            request=request,
            app=SocialApp(
                provider="google",
                name="Google",
                client_id="test-client",
                secret="test-secret",
            ),
        )
        first = SocialLogin(
            user=get_user_model()(
                username="social-student", is_staff=True, is_superuser=True
            ),
            account=SocialAccount(provider="google", uid="google-123"),
            provider=provider,
        )

        with context.request_context(request):
            saved = HangarinSocialAccountAdapter(request).save_user(request, first)

        saved.refresh_from_db()
        self.assertFalse(saved.is_staff)
        self.assertFalse(saved.is_superuser)
        self.assertTrue(
            SocialAccount.objects.filter(
                user=saved, provider="google", uid="google-123"
            ).exists()
        )

        repeat = SocialLogin(
            user=get_user_model()(),
            account=SocialAccount(provider="google", uid="google-123"),
            provider=provider,
        )
        with context.request_context(request):
            repeat.lookup()
        self.assertEqual(repeat.user, saved)

    def test_verified_provider_email_does_not_merge_into_local_account(self):
        local_user = get_user_model().objects.create_user(
            "local-user", email="same@example.com", password="Local-pass-42"
        )
        request = request_with_session()
        provider = GoogleProvider(
            request=request,
            app=SocialApp(
                provider="google",
                name="Google",
                client_id="test-client",
                secret="test-secret",
            ),
        )
        sociallogin = SocialLogin(
            user=get_user_model()(username="provider-user", email="same@example.com"),
            account=SocialAccount(provider="google", uid="different-google-user"),
            provider=provider,
        )

        with context.request_context(request):
            sociallogin.lookup()

        self.assertNotEqual(sociallogin.user, local_user)
        self.assertIsNone(sociallogin.user.pk)


class SocialProviderConfigurationTests(TestCase):
    def test_unconfigured_providers_are_not_listed(self):
        request = request_with_session()

        providers = get_adapter(request).list_providers(request)

        self.assertEqual(providers, [])

    @override_settings(
        SOCIALACCOUNT_PROVIDERS={
            "google": {
                "APPS": [
                    {
                        "client_id": "google-client",
                        "secret": "google-secret",
                        "key": "",
                    }
                ],
                "SCOPE": ["profile", "email"],
                "OAUTH_PKCE_ENABLED": True,
            },
            "github": {
                "APPS": [
                    {
                        "client_id": "github-client",
                        "secret": "github-secret",
                        "key": "",
                    }
                ],
                "SCOPE": ["user:email"],
            },
        }
    )
    def test_configured_google_and_github_are_listed_without_database_apps(self):
        SocialApp.objects.create(
            provider="google",
            name="database-copy",
            client_id="database-client",
            secret="database-secret",
        )
        request = request_with_session()

        providers = get_adapter(request).list_providers(request)

        self.assertEqual({provider.id for provider in providers}, {"google", "github"})
        self.assertTrue(all(provider.app.pk is None for provider in providers))

    @override_settings(
        CSRF_FAILURE_VIEW="tasks.tests.test_registration.csrf_failure_for_test",
        SOCIALACCOUNT_PROVIDERS={
            "google": {
                "APPS": [
                    {
                        "client_id": "google-client",
                        "secret": "google-secret",
                        "key": "",
                    }
                ],
                "SCOPE": ["profile", "email"],
                "OAUTH_PKCE_ENABLED": True,
            }
        }
    )
    def test_provider_login_needs_csrf_and_external_next_is_not_stashed(self):
        client = Client(enforce_csrf_checks=True)
        login_url = reverse("google_login")

        self.assertEqual(client.post(login_url).status_code, 403)
        confirmation = client.get(login_url)
        self.assertEqual(confirmation.status_code, 200)
        token = client.cookies["csrftoken"].value
        response = client.post(
            login_url,
            {"next": "https://evil.example/phish"},
            HTTP_X_CSRFTOKEN=token,
        )

        self.assertEqual(response.status_code, 302)
        self.assertIn("accounts.google.com", response.url)
        self.assertNotIn("evil.example", json.dumps(dict(client.session)))

    def test_security_settings_disable_token_storage_and_email_auto_merge(self):
        self.assertFalse(settings.SOCIALACCOUNT_STORE_TOKENS)
        self.assertFalse(settings.SOCIALACCOUNT_EMAIL_AUTHENTICATION)
        self.assertFalse(settings.SOCIALACCOUNT_EMAIL_AUTHENTICATION_AUTO_CONNECT)
        self.assertFalse(settings.SOCIALACCOUNT_LOGIN_ON_GET)

    def test_partial_production_provider_credentials_fail_closed(self):
        environment = os.environ.copy()
        environment.update(
            {
                "DJANGO_SETTINGS_MODULE": "hangarin.settings",
                "DJANGO_ENV": "production",
                "DJANGO_SECRET_KEY": "production-secret-value-not-for-source-control",
                "DJANGO_DEBUG": "False",
                "DJANGO_ALLOWED_HOSTS": "hangarin.example.com",
                "DJANGO_CSRF_TRUSTED_ORIGINS": "https://hangarin.example.com",
                "GOOGLE_OAUTH_CLIENT_ID": "only-a-client-id",
                "GOOGLE_OAUTH_CLIENT_SECRET": "",
                "GITHUB_OAUTH_CLIENT_ID": "",
                "GITHUB_OAUTH_CLIENT_SECRET": "",
            }
        )

        result = subprocess.run(
            [
                sys.executable,
                "-c",
                "from django.conf import settings; print(settings.DEBUG)",
            ],
            cwd=BASE_DIR,
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("GOOGLE_OAUTH_CLIENT", result.stderr)
