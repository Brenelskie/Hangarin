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
                        "registration/login.html": "<form method='post'>{% csrf_token %}{{ form }}<button>Login</button></form>",
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
            f'{reverse("login")}?next={reverse("dashboard")}',
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
                self.assertTrue(response.url.startswith(reverse("login")))

    def test_disabled_user_is_treated_as_logged_out(self):
        self.client.force_login(self.disabled)

        response = self.client.get(reverse("dashboard"))

        self.assertRedirects(
            response,
            f'{reverse("login")}?next={reverse("dashboard")}',
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
            reverse("login"),
            {"username": "student", "password": "secret123", "next": reverse("task-list")},
        )
        self.assertRedirects(safe_response, reverse("task-list"))
        self.client.logout()

        unsafe_response = self.client.post(
            f'{reverse("login")}?next=https://evil.example/phish',
            {"username": "student", "password": "secret123"},
        )
        self.assertRedirects(unsafe_response, reverse("dashboard"))

    def test_invalid_login_does_not_authenticate_or_reveal_account_state(self):
        response = self.client.post(
            reverse("login"),
            {"username": "student", "password": "wrong-password"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertContains(response, "Please enter a correct username and password")

    def test_logout_requires_post_and_get_does_not_end_session(self):
        self.client.force_login(self.user)

        get_response = self.client.get(reverse("logout"))
        self.assertEqual(get_response.status_code, 405)
        self.assertIn("_auth_user_id", self.client.session)

        post_response = self.client.post(reverse("logout"))
        self.assertRedirects(post_response, reverse("login"))
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_signup_reset_and_social_routes_are_not_mounted(self):
        for path in (
            "/accounts/signup/",
            "/accounts/password/reset/",
            "/accounts/google/login/",
            "/accounts/github/login/",
        ):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 404)

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
