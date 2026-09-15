from datetime import timedelta

from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.test import TestCase
from django.utils import timezone

from tasks.models import Category, Note, Priority, StatusChoices, SubTask, Task


class ModelContractTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.priority = Priority.objects.create(name="high")
        cls.category = Category.objects.create(name="School")
        cls.task = Task.objects.create(
            title="Submit database activity",
            description="Finish and review the activity before submission.",
            deadline=timezone.now() + timedelta(days=2),
            priority=cls.priority,
            category=cls.category,
        )

    def test_base_model_adds_indexed_timestamps_to_every_model(self):
        instances = (
            self.priority,
            self.category,
            self.task,
            Note.objects.create(task=self.task, content="Review the ERD."),
            SubTask.objects.create(parent_task=self.task, title="Run tests"),
        )

        for instance in instances:
            with self.subTest(model=type(instance).__name__):
                self.assertIsNotNone(instance.created_at)
                self.assertIsNotNone(instance.updated_at)
                self.assertTrue(instance._meta.get_field("created_at").db_index)
                self.assertTrue(instance._meta.get_field("updated_at").db_index)

    def test_task_and_subtask_default_to_pending(self):
        subtask = SubTask.objects.create(parent_task=self.task, title="Check spelling")

        self.assertEqual(self.task.status, StatusChoices.PENDING)
        self.assertEqual(subtask.status, StatusChoices.PENDING)
        self.assertEqual(
            list(StatusChoices.values), ["Pending", "In Progress", "Completed"]
        )

    def test_database_rejects_invalid_status_values(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Task.objects.create(
                title="Invalid task",
                description="This status must not be stored.",
                deadline=timezone.now(),
                status="pending ",
                priority=self.priority,
                category=self.category,
            )

        with self.assertRaises(IntegrityError), transaction.atomic():
            SubTask.objects.create(
                title="Invalid subtask",
                status="Unknown",
                parent_task=self.task,
            )

    def test_lookup_names_are_unique(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Priority.objects.create(name="high")

        with self.assertRaises(IntegrityError), transaction.atomic():
            Category.objects.create(name="School")

    def test_models_and_plural_labels_are_readable(self):
        note = Note.objects.create(
            task=self.task,
            content="Bring the printed rubric to class for the final review.",
        )
        subtask = SubTask.objects.create(
            parent_task=self.task,
            title="Review formatting",
        )

        self.assertEqual(str(self.priority), "high")
        self.assertEqual(str(self.category), "School")
        self.assertEqual(str(self.task), "Submit database activity")
        self.assertIn("Submit database activity", str(note))
        self.assertIn("Bring the printed rubric", str(note))
        self.assertEqual(
            str(subtask), "Review formatting — Submit database activity"
        )
        self.assertEqual(Priority._meta.verbose_name_plural, "Priorities")
        self.assertEqual(Category._meta.verbose_name_plural, "Categories")

    def test_referenced_lookups_are_protected(self):
        with self.assertRaises(ProtectedError):
            self.priority.delete()
        with self.assertRaises(ProtectedError):
            self.category.delete()

        self.assertTrue(Task.objects.filter(pk=self.task.pk).exists())

    def test_deleting_task_cascades_to_children(self):
        note = Note.objects.create(task=self.task, content="Temporary note")
        subtask = SubTask.objects.create(parent_task=self.task, title="Temporary child")

        self.task.delete()

        self.assertFalse(Note.objects.filter(pk=note.pk).exists())
        self.assertFalse(SubTask.objects.filter(pk=subtask.pk).exists())

    def test_deleting_a_child_keeps_its_task(self):
        note = Note.objects.create(task=self.task, content="Delete only this note")
        subtask = SubTask.objects.create(parent_task=self.task, title="Delete only this")

        note.delete()
        subtask.delete()

        self.assertTrue(Task.objects.filter(pk=self.task.pk).exists())
