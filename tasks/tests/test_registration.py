import json
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

from allauth.core import context
from allauth.socialaccount.adapter import get_adapter
from allauth.socialaccount.models import SocialAccount, SocialApp, SocialLogin
from allauth.socialaccount.providers.google.provider import GoogleProvider
from allauth.socialaccount.providers.github.views import GitHubOAuth2Adapter
from allauth.socialaccount.providers.google.views import GoogleOAuth2Adapter
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
from hangarin.forms import HangarinSocialSignupForm


def request_with_session(path="/"):
    request = RequestFactory().get(path)
    SessionMiddleware(lambda req: None).process_request(request)
    request.session.save()
    return request


def csrf_failure_for_test(request, reason=""):
    return HttpResponse(status=403)


class SocialSignupFormTests(TestCase):
    @override_settings(
        SOCIALACCOUNT_PROVIDERS={
            "google": {
                "APPS": [
                    {
                        "client_id": "test-client",
                        "secret": "test-secret",
                        "key": "",
                    }
                ],
                "SCOPE": ["profile", "email"],
                "OAUTH_PKCE_ENABLED": True,
            }
        }
    )
    def test_social_signup_form_supports_username_only_accounts(self):
        provider = GoogleProvider(
            request=request_with_session(),
            app=SocialApp(
                provider="google",
                name="Google",
                client_id="test-client",
                secret="test-secret",
            ),
        )
        self.assertEqual(
            settings.SOCIALACCOUNT_FORMS["signup"],
            "hangarin.forms.HangarinSocialSignupForm",
        )
        sociallogin = SocialLogin(
            user=get_user_model()(
                username="google-user",
                email="google-user@example.com",
            ),
            account=SocialAccount(provider="google", uid="google-user"),
            provider=provider,
        )

        form = HangarinSocialSignupForm(sociallogin=sociallogin)

        self.assertIn("username", form.fields)
        self.assertNotIn("email", form.fields)

        session = self.client.session
        session["socialaccount_sociallogin"] = sociallogin.serialize()
        session.save()

        response = self.client.get(reverse("socialaccount_signup"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "socialaccount/signup.html")
        self.assertContains(response, "Choose your Hangarin username")


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
    @override_settings(SOCIALACCOUNT_PROVIDERS={})
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
        self.assertTrue(
            settings.SOCIALACCOUNT_PROVIDERS["google"]["OAUTH_PKCE_ENABLED"]
        )
        self.assertTrue(
            settings.SOCIALACCOUNT_PROVIDERS["github"]["OAUTH_PKCE_ENABLED"]
        )


@override_settings(
    SOCIALACCOUNT_PROVIDERS={
        "google": {
            "APPS": [
                {
                    "client_id": "test-google-client",
                    "secret": "test-google-secret",
                    "key": "",
                }
            ],
            "SCOPE": ["profile", "email"],
            "OAUTH_PKCE_ENABLED": True,
        },
        "github": {
            "APPS": [
                {
                    "client_id": "test-github-client",
                    "secret": "test-github-secret",
                    "key": "",
                }
            ],
            "SCOPE": ["user:email"],
            "OAUTH_PKCE_ENABLED": True,
        },
    }
)
class SocialCallbackFlowTests(TestCase):
    provider_cases = (
        (
            "google",
            "google_login",
            "google_callback",
            GoogleOAuth2Adapter,
        ),
        (
            "github",
            "github_login",
            "github_callback",
            GitHubOAuth2Adapter,
        ),
    )

    def provider_payload(self, provider_name, uid, email):
        if provider_name == "google":
            payload = {
                "sub": uid,
                "given_name": "Test",
                "family_name": "Student",
            }
            if email:
                payload.update({"email": email, "email_verified": True})
            return payload
        payload = {
            "id": uid,
            "login": f"github-{uid}",
            "name": "Test Student",
        }
        if email:
            payload.update(
                {
                    "email": email,
                    "emails": [
                        {
                            "email": email,
                            "primary": True,
                            "verified": True,
                        }
                    ],
                }
            )
        return payload

    def complete_callback(
        self,
        client,
        login_route,
        callback_route,
        adapter_class,
        payload,
    ):
        initiation = client.post(f'{reverse(login_route)}?process=login')
        self.assertEqual(initiation.status_code, 302)
        state = parse_qs(urlparse(initiation.url).query)["state"][0]

        def complete_login(adapter, request, app, token, **kwargs):
            return adapter.get_provider().sociallogin_from_response(request, payload)

        with (
            patch.object(
                adapter_class,
                "get_access_token_data",
                autospec=True,
                return_value={"access_token": "test-access-token"},
            ),
            patch.object(
                adapter_class,
                "complete_login",
                autospec=True,
                side_effect=complete_login,
            ),
        ):
            return client.get(
                reverse(callback_route),
                {"state": state, "code": "test-authorization-code"},
            )

    def test_google_and_github_callbacks_preserve_account_boundaries(self):
        for (
            provider_name,
            login_route,
            callback_route,
            adapter_class,
        ) in self.provider_cases:
            with self.subTest(provider=provider_name, scenario="first login"):
                uid = f"{provider_name}-first-identity"
                email = f"{provider_name}-first@example.com"
                first_client = Client()
                first_response = self.complete_callback(
                    first_client,
                    login_route,
                    callback_route,
                    adapter_class,
                    self.provider_payload(provider_name, uid, email),
                )

                if first_response.url == reverse("socialaccount_signup"):
                    first_response = first_client.post(
                        reverse("socialaccount_signup"),
                        {"username": f"{provider_name}-first-user"},
                    )

                self.assertRedirects(first_response, reverse("dashboard"))
                social_account = SocialAccount.objects.get(
                    provider=provider_name,
                    uid=uid,
                )
                first_user = social_account.user
                self.assertFalse(first_user.is_staff)
                self.assertFalse(first_user.is_superuser)
                self.assertEqual(
                    int(first_client.session["_auth_user_id"]),
                    first_user.pk,
                )

            with self.subTest(provider=provider_name, scenario="repeat login"):
                repeat_client = Client()
                repeat_response = self.complete_callback(
                    repeat_client,
                    login_route,
                    callback_route,
                    adapter_class,
                    self.provider_payload(provider_name, uid, email),
                )

                self.assertRedirects(repeat_response, reverse("dashboard"))
                self.assertEqual(
                    int(repeat_client.session["_auth_user_id"]),
                    first_user.pk,
                )
                self.assertEqual(
                    SocialAccount.objects.filter(
                        provider=provider_name,
                        uid=uid,
                    ).count(),
                    1,
                )

            with self.subTest(provider=provider_name, scenario="email collision"):
                collision_email = f"{provider_name}-local@example.com"
                local_user = get_user_model().objects.create_user(
                    f"{provider_name}-local-user",
                    email=collision_email,
                    password="Local-pass-42",
                )
                collision_client = Client()
                collision_response = self.complete_callback(
                    collision_client,
                    login_route,
                    callback_route,
                    adapter_class,
                    self.provider_payload(
                        provider_name,
                        f"{provider_name}-different-identity",
                        collision_email,
                    ),
                )

                self.assertNotEqual(
                    collision_client.session.get("_auth_user_id"),
                    str(local_user.pk),
                )
                self.assertFalse(
                    SocialAccount.objects.filter(user=local_user).exists()
                )
                self.assertIn(collision_response.status_code, (200, 302))

    def test_duplicate_email_completion_is_blocked_for_both_providers(self):
        for (
            provider_name,
            login_route,
            callback_route,
            adapter_class,
        ) in self.provider_cases:
            with self.subTest(provider=provider_name):
                email = f"{provider_name}-collision@example.com"
                get_user_model().objects.create_user(
                    f"{provider_name}-existing",
                    email=email,
                    password="Local-pass-42",
                )
                user_count = get_user_model().objects.count()
                social_count = SocialAccount.objects.count()
                client = Client()

                callback_response = self.complete_callback(
                    client,
                    login_route,
                    callback_route,
                    adapter_class,
                    self.provider_payload(
                        provider_name,
                        f"{provider_name}-collision-identity",
                        email,
                    ),
                )

                self.assertRedirects(
                    callback_response,
                    reverse("socialaccount_signup"),
                    fetch_redirect_response=False,
                )
                completion_response = client.post(
                    reverse("socialaccount_signup"),
                    {"username": f"{provider_name}-different-person"},
                )

                self.assertEqual(completion_response.status_code, 200)
                self.assertTemplateUsed(
                    completion_response,
                    "socialaccount/signup.html",
                )
                self.assertContains(
                    completion_response,
                    "Sign in using the method that created the original account.",
                )
                self.assertEqual(get_user_model().objects.count(), user_count)
                self.assertEqual(SocialAccount.objects.count(), social_count)
                self.assertNotIn("_auth_user_id", client.session)

    def test_google_and_github_authorization_requests_use_pkce(self):
        for provider_name, login_route, _, _ in self.provider_cases:
            with self.subTest(provider=provider_name):
                client = Client()
                response = client.post(f'{reverse(login_route)}?process=login')

                self.assertEqual(response.status_code, 302)
                parameters = parse_qs(urlparse(response.url).query)
                self.assertEqual(parameters["code_challenge_method"], ["S256"])
                self.assertTrue(parameters["code_challenge"][0])
                state_id = parameters["state"][0]
                state = client.session["socialaccount_states"][state_id][0]
                self.assertTrue(state["pkce_code_verifier"])

    def test_missing_provider_email_requires_completion_for_both_providers(self):
        for (
            provider_name,
            login_route,
            callback_route,
            adapter_class,
        ) in self.provider_cases:
            with self.subTest(provider=provider_name):
                client = Client()
                user_count = get_user_model().objects.count()
                social_count = SocialAccount.objects.count()

                response = self.complete_callback(
                    client,
                    login_route,
                    callback_route,
                    adapter_class,
                    self.provider_payload(
                        provider_name,
                        f"{provider_name}-missing-email",
                        None,
                    ),
                )

                self.assertRedirects(
                    response,
                    reverse("socialaccount_signup"),
                    fetch_redirect_response=False,
                )
                completion = client.get(reverse("socialaccount_signup"))
                self.assertEqual(completion.status_code, 200)
                self.assertTemplateUsed(completion, "socialaccount/signup.html")
                self.assertEqual(get_user_model().objects.count(), user_count)
                self.assertEqual(SocialAccount.objects.count(), social_count)
                self.assertNotIn("_auth_user_id", client.session)

    def test_conflicting_github_username_requires_completion(self):
        get_user_model().objects.create_user(
            "taken-provider-name",
            password="Local-pass-42",
        )
        client = Client()
        payload = self.provider_payload(
            "github",
            "github-conflicting-username",
            "unique-provider@example.com",
        )
        payload["login"] = "taken-provider-name"
        user_count = get_user_model().objects.count()

        response = self.complete_callback(
            client,
            "github_login",
            "github_callback",
            GitHubOAuth2Adapter,
            payload,
        )

        self.assertRedirects(
            response,
            reverse("socialaccount_signup"),
            fetch_redirect_response=False,
        )
        completion = client.get(reverse("socialaccount_signup"))
        self.assertEqual(completion.status_code, 200)
        self.assertTemplateUsed(completion, "socialaccount/signup.html")
        self.assertEqual(get_user_model().objects.count(), user_count)
        self.assertFalse(
            SocialAccount.objects.filter(
                provider="github",
                uid="github-conflicting-username",
            ).exists()
        )
        self.assertNotIn("_auth_user_id", client.session)
