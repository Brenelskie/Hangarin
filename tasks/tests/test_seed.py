from contextlib import redirect_stdout
from datetime import datetime
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from django.utils import timezone

from tasks.models import Category, Note, Priority, StatusChoices, SubTask, Task


REQUIRED_PRIORITIES = ("high", "medium", "low", "critical", "optional")
REQUIRED_CATEGORIES = ("Work", "School", "Personal", "Finance", "Projects")


class InitialDataCommandTests(TestCase):
    def create_required_lookups(self):
        for name in REQUIRED_PRIORITIES:
            Priority.objects.create(name=name)
        for name in REQUIRED_CATEGORIES:
            Category.objects.create(name=name)

    def run_command(self):
        output = StringIO()
        with redirect_stdout(output):
            call_command("create_initial_data")
        return output.getvalue()

    @override_settings(IS_PRODUCTION=True, ALLOW_PRODUCTION_SEED=False)
    def test_production_generation_requires_explicit_temporary_opt_in(self):
        self.create_required_lookups()

        with self.assertRaisesMessage(
            CommandError,
            "Demo generation is disabled in production",
        ):
            self.run_command()

        self.assertEqual(Task.objects.count(), 0)
        self.assertEqual(Note.objects.count(), 0)
        self.assertEqual(SubTask.objects.count(), 0)

    def test_missing_lookups_fail_before_any_demo_write(self):
        Priority.objects.create(name="high")
        for name in REQUIRED_CATEGORIES:
            Category.objects.create(name=name)

        with self.assertRaisesMessage(
            CommandError,
            "Missing required Priority values: medium, low, critical, optional",
        ):
            self.run_command()

        self.assertEqual(Task.objects.count(), 0)
        self.assertEqual(Note.objects.count(), 0)
        self.assertEqual(SubTask.objects.count(), 0)
        self.assertEqual(Priority.objects.count(), 1)
        self.assertEqual(Category.objects.count(), len(REQUIRED_CATEGORIES))

    def test_lookup_validation_requires_exact_category_names(self):
        for name in REQUIRED_PRIORITIES:
            Priority.objects.create(name=name)
        for name in REQUIRED_CATEGORIES:
            Category.objects.create(name=name.lower())

        with self.assertRaisesMessage(
            CommandError,
            "Missing required Category values: Work, School, Personal, Finance, Projects",
        ):
            self.run_command()

        self.assertEqual(Task.objects.count(), 0)
        self.assertEqual(Note.objects.count(), 0)
        self.assertEqual(SubTask.objects.count(), 0)

    def test_first_run_creates_valid_related_demo_records(self):
        self.create_required_lookups()

        output = self.run_command()

        self.assertEqual(Task.objects.count(), 10)
        self.assertEqual(Note.objects.count(), 10)
        self.assertEqual(SubTask.objects.count(), 20)
        self.assertIn("Created 10 tasks, 10 notes, and 20 subtasks", output)

        current_local_time = timezone.localtime(timezone.now())
        for task in Task.objects.select_related("priority", "category"):
            with self.subTest(task=task.pk):
                self.assertTrue(task.title)
                self.assertTrue(task.description)
                self.assertIn(task.status, StatusChoices.values)
                self.assertIn(task.priority.name, REQUIRED_PRIORITIES)
                self.assertIn(task.category.name, REQUIRED_CATEGORIES)
                self.assertTrue(timezone.is_aware(task.deadline))
                local_deadline = timezone.localtime(task.deadline)
                self.assertEqual(
                    (local_deadline.year, local_deadline.month),
                    (current_local_time.year, current_local_time.month),
                )
                self.assertEqual(task.notes.count(), 1)
                self.assertEqual(task.subtasks.count(), 2)
                self.assertTrue(task.notes.get().content)
                self.assertTrue(
                    all(
                        subtask.status in StatusChoices.values
                        for subtask in task.subtasks.all()
                    )
                )

    def test_second_run_keeps_counts_and_preserves_existing_data(self):
        self.create_required_lookups()
        self.run_command()
        first_task = Task.objects.order_by("pk").first()
        first_task.title = "Keep my edited title"
        first_task.save(update_fields=("title", "updated_at"))
        original_counts = (
            Task.objects.count(),
            Note.objects.count(),
            SubTask.objects.count(),
        )

        output = self.run_command()

        self.assertEqual(
            (
                Task.objects.count(),
                Note.objects.count(),
                SubTask.objects.count(),
            ),
            original_counts,
        )
        first_task.refresh_from_db()
        self.assertEqual(first_task.title, "Keep my edited title")
        self.assertIn("unchanged", output.lower())
        self.assertIn("10 tasks, 10 notes, and 20 subtasks", output)

    def test_generation_is_deterministic_for_the_current_month(self):
        self.create_required_lookups()
        self.run_command()
        first_signature = self.demo_signature()

        Task.objects.all().delete()
        self.run_command()

        self.assertEqual(self.demo_signature(), first_signature)

    def test_existing_child_row_alone_triggers_rerun_guard(self):
        self.create_required_lookups()
        task = Task.objects.create(
            title="User-created task",
            description="This must not be replaced.",
            deadline=timezone.make_aware(datetime(2026, 9, 30, 12, 0)),
            priority=Priority.objects.get(name="high"),
            category=Category.objects.get(name="School"),
        )
        note = Note.objects.create(task=task, content="Keep this note")

        output = self.run_command()

        self.assertEqual(Task.objects.count(), 1)
        self.assertEqual(Note.objects.count(), 1)
        self.assertEqual(SubTask.objects.count(), 0)
        self.assertTrue(
            Note.objects.filter(pk=note.pk, content="Keep this note").exists()
        )
        self.assertIn("unchanged", output.lower())

    def test_mid_generation_failure_rolls_back_all_demo_rows(self):
        self.create_required_lookups()

        from tasks.management.commands.create_initial_data import Command

        with patch.object(
            Command,
            "_after_task_created",
            side_effect=RuntimeError("injected failure"),
        ):
            with self.assertRaisesMessage(RuntimeError, "injected failure"):
                self.run_command()

        self.assertEqual(Task.objects.count(), 0)
        self.assertEqual(Note.objects.count(), 0)
        self.assertEqual(SubTask.objects.count(), 0)

    def demo_signature(self):
        signature = []
        tasks = Task.objects.select_related("priority", "category").order_by("pk")
        for task in tasks:
            signature.append(
                (
                    task.title,
                    task.description,
                    task.deadline.isoformat(),
                    task.status,
                    task.priority.name,
                    task.category.name,
                    task.notes.get().content,
                    tuple(
                        task.subtasks.order_by("pk").values_list(
                            "title", "status"
                        )
                    ),
                )
            )
        return signature
