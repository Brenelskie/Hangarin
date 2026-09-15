from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from faker import Faker

from tasks.models import Category, Note, Priority, StatusChoices, SubTask, Task


REQUIRED_PRIORITIES = ("high", "medium", "low", "critical", "optional")
REQUIRED_CATEGORIES = ("Work", "School", "Personal", "Finance", "Projects")
TASK_COUNT = 10
NOTES_PER_TASK = 1
SUBTASKS_PER_TASK = 2
FAKER_SEED = 20260915


class Command(BaseCommand):
    help = "Create deterministic Hangarin demo tasks after required lookups exist."

    def handle(self, *args, **options):
        if settings.IS_PRODUCTION and not settings.ALLOW_PRODUCTION_SEED:
            raise CommandError(
                "Demo generation is disabled in production. Set "
                "HANGARIN_ALLOW_PRODUCTION_SEED=True only for a reviewed, "
                "empty first launch, then set it back to False."
            )

        existing_counts = self._demo_counts()
        if any(existing_counts):
            self.stdout.write(
                self.style.WARNING(
                    "Demo data unchanged: "
                    f"{existing_counts[0]} tasks, "
                    f"{existing_counts[1]} notes, and "
                    f"{existing_counts[2]} subtasks already exist."
                )
            )
            return

        priorities, categories = self._required_lookups()
        faker = Faker("en_US")
        faker.seed_instance(FAKER_SEED)

        with transaction.atomic():
            self._generate_records(faker, priorities, categories)

        created_counts = self._demo_counts()
        self.stdout.write(
            self.style.SUCCESS(
                f"Created {created_counts[0]} tasks, "
                f"{created_counts[1]} notes, and "
                f"{created_counts[2]} subtasks."
            )
        )

    def _demo_counts(self):
        return (
            Task.objects.count(),
            Note.objects.count(),
            SubTask.objects.count(),
        )

    def _required_lookups(self):
        priorities = Priority.objects.in_bulk(REQUIRED_PRIORITIES, field_name="name")
        categories = Category.objects.in_bulk(REQUIRED_CATEGORIES, field_name="name")

        missing_messages = []
        missing_priorities = [
            name for name in REQUIRED_PRIORITIES if name not in priorities
        ]
        missing_categories = [
            name for name in REQUIRED_CATEGORIES if name not in categories
        ]
        if missing_priorities:
            missing_messages.append(
                "Missing required Priority values: " + ", ".join(missing_priorities)
            )
        if missing_categories:
            missing_messages.append(
                "Missing required Category values: " + ", ".join(missing_categories)
            )
        if missing_messages:
            raise CommandError(
                "; ".join(missing_messages)
                + ". Create these exact values in Django Admin before rerunning."
            )

        return priorities, categories

    def _generate_records(self, faker, priorities, categories):
        timezone_info = timezone.get_current_timezone()
        statuses = tuple(StatusChoices.values)

        for _ in range(TASK_COUNT):
            task = Task.objects.create(
                title=faker.sentence(),
                description=faker.paragraph(),
                deadline=faker.date_time_this_month(
                    before_now=True,
                    after_now=True,
                    tzinfo=timezone_info,
                ),
                status=faker.random_element(statuses),
                priority=priorities[faker.random_element(REQUIRED_PRIORITIES)],
                category=categories[faker.random_element(REQUIRED_CATEGORIES)],
            )
            self._after_task_created(task)

            for _ in range(NOTES_PER_TASK):
                Note.objects.create(task=task, content=faker.paragraph())

            for _ in range(SUBTASKS_PER_TASK):
                SubTask.objects.create(
                    parent_task=task,
                    title=faker.sentence(nb_words=4),
                    status=faker.random_element(statuses),
                )

    def _after_task_created(self, task):
        """Test seam invoked inside the transaction after each parent insert."""
