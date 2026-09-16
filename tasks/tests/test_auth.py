from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from tasks.models import Category, Note, Priority, SubTask, Task


TEST_TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "APP_DIRS": False,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
            "loaders": [
                (
                    "django.template.loaders.locmem.Loader",
                    {
                        "account/login.html": "<form method='post'>{% csrf_token %}{{ form }}<button>Login</button></form>",
                        "account/logout.html": "<form method='post'>{% csrf_token %}<button>Logout</button></form>",
                        "tasks/dashboard.html": "Dashboard {{ task_count }}",
                        "tasks/task_list.html": "{% for task in tasks %}{{ task.title }}{% endfor %}",
                        "tasks/priority_list.html": "{% for item in priorities %}{{ item }}{% endfor %}",
                        "tasks/category_list.html": "{% for item in categories %}{{ item }}{% endfor %}",
                        "tasks/note_list.html": "{% for item in notes %}{{ item }}{% endfor %}",
                        "tasks/subtask_list.html": "{% for item in subtasks %}{{ item }}{% endfor %}",
                        "tasks/task_detail.html": "{{ task.title }}",
                        "tasks/entity_form.html": "<form method='post'>{% csrf_token %}{{ form }}<button>Save</button></form>",
                        "tasks/confirm_delete.html": "<form method='post'>{% csrf_token %}<button>Delete</button></form>",
                    },
                )
            ],
        },
    }
]

ADMIN_TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ]
        },
    }
]


@override_settings(TEMPLATES=TEST_TEMPLATES)
class AuthenticationContractTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(
            "student", password="secret123"
        )
        cls.staff = get_user_model().objects.create_user(
            "staff", password="secret123", is_staff=True
        )
        cls.disabled = get_user_model().objects.create_user(
            "disabled", password="secret123", is_active=False
        )
        cls.priority = Priority.objects.create(name="high")
        cls.category = Category.objects.create(name="School")
        cls.task = Task.objects.create(
            title="Protected task",
            description="Only signed-in users may see this.",
            deadline=timezone.now(),
            priority=cls.priority,
            category=cls.category,
        )
        cls.note = Note.objects.create(task=cls.task, content="Protected note")
        cls.subtask = SubTask.objects.create(
            title="Protected subtask", parent_task=cls.task
        )

    def test_anonymous_dashboard_redirects_to_login(self):
        response = self.client.get(reverse("dashboard"))

        self.assertRedirects(
            response,
            f'{reverse("account_login")}?next={reverse("dashboard")}',
        )

    def test_active_user_can_open_dashboard(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("dashboard"))

        self.assertEqual(response.status_code, 200)

    def test_every_custom_route_requires_login(self):
        protected_urls = (
            reverse("dashboard"),
            reverse("task-list"),
            reverse("task-add"),
            reverse("task-detail", args=(self.task.pk,)),
            reverse("task-edit", args=(self.task.pk,)),
            reverse("task-delete", args=(self.task.pk,)),
            reverse("priority-list"),
            reverse("priority-add"),
            reverse("priority-edit", args=(self.priority.pk,)),
            reverse("priority-delete", args=(self.priority.pk,)),
            reverse("category-list"),
            reverse("category-add"),
            reverse("category-edit", args=(self.category.pk,)),
            reverse("category-delete", args=(self.category.pk,)),
            reverse("note-list"),
            reverse("note-add"),
            reverse("subtask-list"),
            reverse("subtask-add"),
        )

        for url in protected_urls:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 302)
                self.assertTrue(response.url.startswith(reverse("account_login")))

    def test_disabled_user_is_treated_as_logged_out(self):
        self.client.force_login(self.disabled)

        response = self.client.get(reverse("dashboard"))

        self.assertRedirects(
            response,
            f'{reverse("account_login")}?next={reverse("dashboard")}',
        )

    def test_custom_site_is_shared_by_active_user_staff_and_superuser(self):
        superuser = get_user_model().objects.create_superuser(
            "root", "root@example.com", "secret123"
        )
        for user in (self.user, self.staff, superuser):
            with self.subTest(user=user.username):
                self.client.force_login(user)
                self.assertEqual(self.client.get(reverse("task-list")).status_code, 200)
                self.client.logout()

    @override_settings(TEMPLATES=ADMIN_TEMPLATES)
    def test_django_admin_remains_staff_only(self):
        self.client.force_login(self.user)
        regular_response = self.client.get(reverse("admin:index"))
        self.client.force_login(self.staff)
        staff_response = self.client.get(reverse("admin:index"))

        self.assertEqual(regular_response.status_code, 302)
        self.assertEqual(staff_response.status_code, 200)

    def test_valid_login_honors_safe_next_and_rejects_external_next(self):
        safe_response = self.client.post(
            reverse("account_login"),
            {"login": "student", "password": "secret123", "next": reverse("task-list")},
        )
        self.assertRedirects(safe_response, reverse("task-list"))
        self.client.logout()

        unsafe_response = self.client.post(
            f'{reverse("account_login")}?next=https://evil.example/phish',
            {"login": "student", "password": "secret123"},
        )
        self.assertRedirects(unsafe_response, reverse("dashboard"))

    def test_invalid_login_does_not_authenticate_or_reveal_account_state(self):
        response = self.client.post(
            reverse("account_login"),
            {"login": "student", "password": "wrong-password"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertContains(
            response,
            "The username and/or password you specified are not correct.",
        )

    def test_logout_requires_post_and_get_does_not_end_session(self):
        self.client.force_login(self.user)

        get_response = self.client.get(reverse("account_logout"))
        self.assertEqual(get_response.status_code, 200)
        self.assertIn("_auth_user_id", self.client.session)

        post_response = self.client.post(reverse("account_logout"))
        self.assertRedirects(post_response, reverse("account_login"))
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_logout_rejects_bad_csrf_without_ending_session(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        logout_url = reverse("account_logout")

        missing_response = client.post(logout_url)
        self.assertEqual(missing_response.status_code, 403)
        self.assertEqual(int(client.session["_auth_user_id"]), self.user.pk)

        client.get(logout_url)
        token = client.cookies["csrftoken"].value
        invalid_response = client.post(
            logout_url,
            HTTP_X_CSRFTOKEN="invalid-csrf-token",
            HTTP_ORIGIN="http://testserver",
        )
        self.assertEqual(invalid_response.status_code, 403)
        self.assertEqual(int(client.session["_auth_user_id"]), self.user.pk)

        cross_origin_response = client.post(
            logout_url,
            HTTP_X_CSRFTOKEN=token,
            HTTP_ORIGIN="https://evil.example",
        )
        self.assertEqual(cross_origin_response.status_code, 403)
        self.assertEqual(int(client.session["_auth_user_id"]), self.user.pk)

        accepted_response = client.post(
            logout_url,
            HTTP_X_CSRFTOKEN=token,
            HTTP_ORIGIN="http://testserver",
        )
        self.assertRedirects(accepted_response, reverse("account_login"))
        self.assertNotIn("_auth_user_id", client.session)

    def test_signup_and_social_routes_are_mounted(self):
        self.assertEqual(reverse("account_signup"), "/accounts/signup/")
        self.assertEqual(reverse("google_login"), "/accounts/google/login/")
        self.assertEqual(reverse("github_login"), "/accounts/github/login/")

    def test_csrf_blocks_task_mutations_and_accepts_same_origin_token(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        payload = {
            "title": "CSRF checked task",
            "description": "A protected write.",
            "deadline": "2026-09-30T12:00",
            "status": "Pending",
            "priority": self.priority.pk,
            "category": self.category.pk,
        }

        missing_response = client.post(reverse("task-add"), payload)
        self.assertEqual(missing_response.status_code, 403)
        self.assertFalse(Task.objects.filter(title="CSRF checked task").exists())

        client.get(reverse("task-add"))
        token = client.cookies["csrftoken"].value
        cross_origin_response = client.post(
            reverse("task-add"),
            payload,
            HTTP_X_CSRFTOKEN=token,
            HTTP_ORIGIN="https://evil.example",
        )
        self.assertEqual(cross_origin_response.status_code, 403)
        self.assertFalse(Task.objects.filter(title="CSRF checked task").exists())

        accepted_response = client.post(
            reverse("task-add"),
            payload,
            HTTP_X_CSRFTOKEN=token,
            HTTP_ORIGIN="http://testserver",
        )
        self.assertEqual(accepted_response.status_code, 302)
        self.assertTrue(Task.objects.filter(title="CSRF checked task").exists())

    def test_all_domain_mutation_routes_reject_missing_csrf_token(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        mutation_urls = (
            reverse("task-add"),
            reverse("task-edit", args=(self.task.pk,)),
            reverse("task-delete", args=(self.task.pk,)),
            reverse("priority-add"),
            reverse("priority-edit", args=(self.priority.pk,)),
            reverse("priority-delete", args=(self.priority.pk,)),
            reverse("category-add"),
            reverse("category-edit", args=(self.category.pk,)),
            reverse("category-delete", args=(self.category.pk,)),
            reverse("note-add"),
            reverse("note-edit", args=(self.note.pk,)),
            reverse("note-delete", args=(self.note.pk,)),
            reverse("subtask-add"),
            reverse("subtask-edit", args=(self.subtask.pk,)),
            reverse("subtask-delete", args=(self.subtask.pk,)),
        )
        original_counts = (
            Task.objects.count(),
            Priority.objects.count(),
            Category.objects.count(),
            Note.objects.count(),
            SubTask.objects.count(),
        )

        for url in mutation_urls:
            with self.subTest(url=url):
                self.assertEqual(client.post(url, {}).status_code, 403)

        self.assertEqual(
            (
                Task.objects.count(),
                Priority.objects.count(),
                Category.objects.count(),
                Note.objects.count(),
                SubTask.objects.count(),
            ),
            original_counts,
        )


class LoginInterfaceTests(TestCase):
    def test_login_is_hangarin_branded_and_links_public_signup(self):
        response = self.client.get(reverse("account_login"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Hangarin")
        self.assertContains(response, "Give every goal a next step")
        self.assertContains(response, f'href="{reverse("account_signup")}"')
        self.assertContains(response, "Skip to main content")
        self.assertNotContains(response, "PSUSphere")
        # Provider actions stay hidden until both environment credentials exist.
        self.assertNotContains(response, "Continue with Google")
        self.assertNotContains(response, "Continue with GitHub")

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
    def test_configured_provider_buttons_are_post_forms_with_csrf(self):
        response = self.client.get(reverse("account_login"))

        self.assertContains(response, "Continue with Google")
        self.assertContains(response, "Continue with GitHub")
        self.assertContains(
            response, f'action="{reverse("google_login")}?process=login"'
        )
        self.assertContains(
            response, f'action="{reverse("github_login")}?process=login"'
        )
        self.assertContains(response, 'name="csrfmiddlewaretoken"', count=3)
        self.assertNotContains(response, f'href="{reverse("google_login")}"')
        self.assertNotContains(response, f'href="{reverse("github_login")}"')

        confirmation = self.client.get(reverse("google_login"))
        self.assertContains(confirmation, "Continue to Google")
        self.assertContains(confirmation, "Cancel and return")

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
    def test_social_connection_process_is_unavailable_before_provider_redirect(self):
        user = get_user_model().objects.create_user(
            "existing-student", password="Current-safe-password-42"
        )
        client = Client(enforce_csrf_checks=True)
        client.force_login(user)

        for route_name in ("google_login", "github_login"):
            url = f'{reverse(route_name)}?process=connect'
            with self.subTest(route_name=route_name, method="get"):
                response = client.get(url)
                self.assertEqual(response.status_code, 200)
                self.assertTemplateUsed(
                    response, "account/feature_unavailable.html"
                )
                self.assertContains(
                    response, "Account connections are not available"
                )
                self.assertNotContains(response, "<form")

            with self.subTest(route_name=route_name, method="post", csrf="missing"):
                self.assertEqual(client.post(url).status_code, 403)

        client.get(reverse("account_change_password"))
        token = client.cookies["csrftoken"].value
        for route_name in ("google_login", "github_login"):
            url = f'{reverse(route_name)}?process=connect'
            with self.subTest(route_name=route_name, method="post", csrf="present"):
                response = client.post(url, HTTP_X_CSRFTOKEN=token)
                self.assertEqual(response.status_code, 403)
                self.assertContains(
                    response,
                    "Account connections are not available",
                    status_code=403,
                )
                self.assertNotIn("accounts.google.com", response.get("Location", ""))
                self.assertNotIn("github.com", response.get("Location", ""))

    def test_social_failure_and_cancel_pages_offer_clear_exits(self):
        pages = (
            (
                "socialaccount_login_error",
                "The provider could not sign you in",
                401,
            ),
            ("socialaccount_login_cancelled", "You stayed in Hangarin", 200),
        )

        for route_name, heading, status_code in pages:
            with self.subTest(route_name=route_name):
                response = self.client.get(reverse(route_name))
                self.assertEqual(response.status_code, status_code)
                self.assertContains(response, heading, status_code=status_code)
                self.assertContains(
                    response,
                    f'href="{reverse("account_login")}"',
                    status_code=status_code,
                )
                self.assertContains(
                    response, "Create a regular account", status_code=status_code
                )

    def test_signup_explains_regular_shared_account_and_no_password_reset_link(self):
        response = self.client.get(reverse("account_signup"))

        self.assertContains(response, "Create a regular account")
        self.assertContains(response, "Registration never creates an administrator account")
        self.assertContains(response, "shared task workspace")
        self.assertNotContains(response, "password/reset")

        login_response = self.client.get(reverse("account_login"))
        self.assertContains(login_response, "Ask a Hangarin administrator")
        self.assertNotContains(login_response, "password/reset")

    @override_settings(DEBUG=False)
    def test_csrf_failure_uses_branded_safe_response(self):
        client = Client(enforce_csrf_checks=True)

        response = client.post(
            reverse("account_login"),
            {"username": "student", "password": "secret123"},
        )

        self.assertEqual(response.status_code, 403)
        self.assertContains(response, "Hangarin", status_code=403)
        self.assertContains(
            response,
            "could not confirm that this request came from you",
            status_code=403,
        )
        self.assertContains(
            response,
            f'href="{reverse("account_login")}"',
            status_code=403,
        )


class AccountManagementInterfaceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(
            "account-student", password="Current-safe-password-42"
        )
        cls.passwordless_user = get_user_model().objects.create_user(
            "provider-student"
        )
        cls.passwordless_user.set_unusable_password()
        cls.passwordless_user.save(update_fields=["password"])

    def test_deferred_account_features_use_branded_unavailable_page(self):
        self.client.force_login(self.user)
        pages = (
            (reverse("account_email"), "Email management is not available"),
            (
                reverse("account_email_verification_sent"),
                "Email verification is not available",
            ),
            (
                reverse("account_confirm_email", kwargs={"key": "sample-key"}),
                "Email verification is not available",
            ),
            (
                reverse("account_reset_password"),
                "Password recovery is not available",
            ),
            (
                reverse("account_reset_password_done"),
                "Password recovery is not available",
            ),
            (
                reverse("account_reset_password_from_key_done"),
                "Password recovery is not available",
            ),
            (
                reverse(
                    "account_reset_password_from_key",
                    kwargs={"uidb36": "abc", "key": "sample-key"},
                ),
                "Password recovery is not available",
            ),
            (
                reverse("socialaccount_connections"),
                "Account connections are not available",
            ),
        )

        for url, heading in pages:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                self.assertTemplateUsed(
                    response, "account/feature_unavailable.html"
                )
                self.assertContains(response, "Hangarin")
                self.assertContains(response, heading)
                self.assertContains(
                    response, f'href="{reverse("dashboard")}"'
                )
                self.assertNotContains(response, "<form")

    def test_deferred_account_features_reject_posts_and_keep_csrf_protection(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        deferred_urls = (
            reverse("account_email"),
            reverse("account_reset_password"),
            reverse("socialaccount_connections"),
        )

        for url in deferred_urls:
            with self.subTest(url=url, csrf="missing"):
                self.assertEqual(client.post(url, {}).status_code, 403)

        client.get(reverse("account_change_password"))
        token = client.cookies["csrftoken"].value
        for url in deferred_urls:
            with self.subTest(url=url, csrf="present"):
                self.assertEqual(
                    client.post(url, {}, HTTP_X_CSRFTOKEN=token).status_code,
                    405,
                )

    def test_password_change_and_reauthentication_are_branded_and_post_only(self):
        self.client.force_login(self.user)
        pages = (
            (
                "account_change_password",
                "account/password_change.html",
                "Change your password",
            ),
            (
                "account_reauthenticate",
                "account/reauthenticate.html",
                "Confirm your identity",
            ),
        )

        for route_name, template_name, heading in pages:
            with self.subTest(route_name=route_name):
                response = self.client.get(reverse(route_name))
                self.assertEqual(response.status_code, 200)
                self.assertTemplateUsed(response, template_name)
                self.assertContains(response, "Hangarin")
                self.assertContains(response, heading)
                self.assertContains(response, 'name="csrfmiddlewaretoken"')
                self.assertContains(
                    response, f'action="{reverse(route_name)}"'
                )

    def test_passwordless_account_gets_branded_set_password_form(self):
        self.client.force_login(self.passwordless_user)

        response = self.client.get(reverse("account_set_password"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "account/password_set.html")
        self.assertContains(response, "Set a Hangarin password")
        self.assertContains(response, 'name="csrfmiddlewaretoken"')
        self.assertContains(
            response, f'action="{reverse("account_set_password")}"'
        )

    def test_inactive_account_page_is_branded(self):
        response = self.client.get(reverse("account_inactive"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "account/account_inactive.html")
        self.assertContains(response, "This account is inactive")
        self.assertContains(response, f'href="{reverse("account_login")}"')


class AuthenticationInterfaceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(
            "student", password="secret123"
        )

    def test_login_uses_hangarin_brand_without_social_or_psusphere_copy(self):
        response = self.client.get(reverse("account_login"))

        self.assertContains(response, "Hangarin")
        self.assertContains(response, 'href="#main-content"')
        self.assertContains(response, "hangarin.css")
        self.assertNotContains(response, "PSUSphere")
        self.assertNotContains(response, "Continue with Google")
        self.assertNotContains(response, "Continue with GitHub")

    def test_authenticated_shell_exposes_shared_context_and_post_logout(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("dashboard"))

        self.assertContains(response, "Shared workspace")
        self.assertContains(response, 'action="%s"' % reverse("account_logout"))
        self.assertContains(response, 'aria-current="page"')
        self.assertContains(response, 'aria-controls="primary-navigation"')
        self.assertContains(response, 'aria-expanded="false"')
        self.assertContains(response, "hangarin.js")

    def test_authenticated_logout_confirmation_uses_account_ui(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("account_logout"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Sign out of Hangarin?")
        self.assertContains(response, f'action="{reverse("account_logout")}"')
        self.assertContains(response, "Return to dashboard")
