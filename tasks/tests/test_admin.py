from django.contrib import admin
from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase
from django.urls import reverse
from django.utils import timezone

from tasks.models import Category, Note, Priority, SubTask, Task


class AdminConfigurationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.staff_user = get_user_model().objects.create_superuser(
            username="admin",
            email="admin@example.com",
            password="test-password",
        )

    def setUp(self):
        self.request = RequestFactory().get("/admin/")
        self.request.user = self.staff_user

    def model_admin(self, model):
        return admin.site._registry[model]

    def test_all_assignment_models_are_registered(self):
        for model in (Task, SubTask, Category, Priority, Note):
            with self.subTest(model=model.__name__):
                self.assertIn(model, admin.site._registry)

    def test_task_admin_matches_assignment_configuration(self):
        model_admin = self.model_admin(Task)

        self.assertEqual(
            model_admin.list_display,
            ("title", "status", "deadline", "priority", "category"),
        )
        self.assertEqual(model_admin.list_filter, ("status", "priority", "category"))
        self.assertEqual(model_admin.search_fields, ("title", "description"))
        self.assertEqual(model_admin.list_select_related, ("priority", "category"))

    def test_subtask_admin_matches_assignment_configuration(self):
        model_admin = self.model_admin(SubTask)

        self.assertEqual(
            model_admin.list_display,
            ("title", "status", "parent_task_name"),
        )
        self.assertEqual(model_admin.list_filter, ("status",))
        self.assertEqual(model_admin.search_fields, ("title",))
        self.assertEqual(model_admin.list_select_related, ("parent_task",))
        self.assertEqual(model_admin.parent_task_name.short_description, "Parent Task")
        self.assertEqual(model_admin.parent_task_name.admin_order_field, "parent_task__title")

    def test_subtask_parent_task_column_returns_readable_title(self):
        priority = Priority.objects.create(name="high")
        category = Category.objects.create(name="School")
        task = Task.objects.create(
            title="Complete Hangarin",
            description="Finish the task manager.",
            deadline=timezone.now(),
            priority=priority,
            category=category,
        )
        subtask = SubTask.objects.create(title="Check admin", parent_task=task)

        self.assertEqual(
            self.model_admin(SubTask).parent_task_name(subtask),
            "Complete Hangarin",
        )

    def test_lookup_admin_pages_are_intentionally_small(self):
        for model in (Category, Priority):
            with self.subTest(model=model.__name__):
                model_admin = self.model_admin(model)
                self.assertEqual(model_admin.list_display, ("name",))
                self.assertEqual(model_admin.search_fields, ("name",))

    def test_note_admin_matches_assignment_configuration(self):
        model_admin = self.model_admin(Note)

        self.assertEqual(model_admin.list_display, ("task", "content", "created_at"))
        self.assertEqual(model_admin.list_filter, ("created_at",))
        self.assertEqual(model_admin.search_fields, ("content",))
        self.assertEqual(model_admin.list_select_related, ("task",))

    def test_admin_uses_readable_plural_labels(self):
        expected_labels = {
            Priority: "Priorities",
            Category: "Categories",
            Task: "tasks",
            Note: "notes",
            SubTask: "Subtasks",
        }

        for model, expected_label in expected_labels.items():
            with self.subTest(model=model.__name__):
                self.assertEqual(model._meta.verbose_name_plural, expected_label)

    def test_admin_forms_accept_required_lookups_and_reject_duplicates(self):
        required_values = {
            Priority: ("high", "medium", "low", "critical", "optional"),
            Category: ("Work", "School", "Personal", "Finance", "Projects"),
        }

        for model, names in required_values.items():
            model_admin = self.model_admin(model)
            form_class = model_admin.get_form(self.request)
            for name in names:
                with self.subTest(model=model.__name__, name=name):
                    form = form_class(data={"name": name})
                    self.assertTrue(form.is_valid(), form.errors)
                    form.save()

            duplicate_form = form_class(data={"name": names[0]})
            self.assertFalse(duplicate_form.is_valid())
            self.assertIn("name", duplicate_form.errors)

    def test_staff_can_open_each_configured_changelist(self):
        priority = Priority.objects.create(name="high")
        category = Category.objects.create(name="School")
        task = Task.objects.create(
            title="Complete Hangarin",
            description="Finish the task manager.",
            deadline=timezone.now(),
            priority=priority,
            category=category,
        )
        Note.objects.create(task=task, content="Review the Admin pages.")
        SubTask.objects.create(title="Check admin", parent_task=task)
        self.client.force_login(self.staff_user)

        for model_name in ("task", "subtask", "category", "priority", "note"):
            with self.subTest(model=model_name):
                response = self.client.get(
                    reverse(f"admin:tasks_{model_name}_changelist")
                )
                self.assertEqual(response.status_code, 200)

        subtask_response = self.client.get(
            reverse("admin:tasks_subtask_changelist")
        )
        self.assertContains(subtask_response, "Parent Task")
        self.assertContains(subtask_response, "Complete Hangarin")
