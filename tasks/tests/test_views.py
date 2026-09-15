from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from tasks.models import Category, Note, Priority, StatusChoices, SubTask, Task
from tasks.tests.test_auth import TEST_TEMPLATES


@override_settings(TEMPLATES=TEST_TEMPLATES)
class TaskQueryContractTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user("student", password="secret123")
        cls.priority = Priority.objects.create(name="high")
        cls.category = Category.objects.create(name="School")
        Task.objects.create(
            title="Write database report",
            description="Finish the final paper",
            deadline=timezone.now(),
            status="Pending",
            priority=cls.priority,
            category=cls.category,
        )
        Task.objects.create(
            title="Buy groceries",
            description="Personal errands",
            deadline=timezone.now(),
            status="Completed",
            priority=cls.priority,
            category=cls.category,
        )

    def setUp(self):
        self.client.force_login(self.user)

    def task_payload(self, **overrides):
        payload = {
            "title": "Prepare Hangarin presentation",
            "description": "Review every task-management flow.",
            "deadline": "2026-09-30T12:00",
            "status": StatusChoices.IN_PROGRESS,
            "priority": self.priority.pk,
            "category": self.category.pk,
        }
        payload.update(overrides)
        return payload

    def test_task_search_filter_and_order_are_composed(self):
        response = self.client.get(
            reverse("task-list"),
            {
                "q": "database",
                "status": "Pending",
                "priority": self.priority.pk,
                "category": self.category.pk,
                "order": "title",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual([task.title for task in response.context["tasks"]], ["Write database report"])
        self.assertIn("status=Pending", response.context["query_string"])

    def test_invalid_query_parameters_fall_back_to_safe_first_page(self):
        response = self.client.get(
            reverse("task-list"),
            {
                "status": "not-a-status",
                "priority": "999999",
                "category": "bad",
                "order": "raw_sql",
                "page": "not-a-page",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["active_query"], {})
        self.assertEqual(response.context["page_obj"].number, 1)
        self.assertEqual(response.context["paginator"].count, 2)

    def test_task_pagination_is_bounded_and_retains_valid_query_state(self):
        for index in range(11):
            Task.objects.create(
                title=f"Paged task {index:02d}",
                description="pagination target",
                deadline=timezone.now() + timedelta(days=index + 1),
                status=StatusChoices.PENDING,
                priority=self.priority,
                category=self.category,
            )

        response = self.client.get(
            reverse("task-list"),
            {"q": "Paged", "status": "Pending", "order": "title", "page": 2},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["page_obj"].number, 2)
        self.assertLessEqual(len(response.context["tasks"]), 10)
        self.assertEqual(
            response.context["query_string"],
            "q=Paged&status=Pending&order=title",
        )

    def test_other_lists_search_their_domain_and_related_task(self):
        other_priority = Priority.objects.create(name="critical")
        other_category = Category.objects.create(name="Projects")
        target_task = Task.objects.create(
            title="Capstone launch",
            description="Ship it",
            deadline=timezone.now(),
            priority=other_priority,
            category=other_category,
        )
        note = Note.objects.create(task=target_task, content="Invite the panel")
        subtask = SubTask.objects.create(title="Prepare slides", parent_task=target_task)

        cases = (
            ("priority-list", "critical", "priorities", other_priority),
            ("category-list", "Projects", "categories", other_category),
            ("note-list", "Capstone", "notes", note),
            ("subtask-list", "Capstone", "subtasks", subtask),
        )
        for route, query, context_name, expected in cases:
            with self.subTest(route=route):
                response = self.client.get(reverse(route), {"q": query})
                self.assertEqual(list(response.context[context_name]), [expected])

    def test_dashboard_reports_counts_and_separates_deadline_queues(self):
        now = timezone.now()
        overdue = Task.objects.create(
            title="Overdue task",
            description="Late",
            deadline=now - timedelta(days=1),
            status=StatusChoices.PENDING,
            priority=self.priority,
            category=self.category,
        )
        upcoming = Task.objects.create(
            title="Upcoming task",
            description="Soon",
            deadline=now + timedelta(days=1),
            status=StatusChoices.IN_PROGRESS,
            priority=self.priority,
            category=self.category,
        )
        completed_late = Task.objects.create(
            title="Completed late task",
            description="Done",
            deadline=now - timedelta(days=2),
            status=StatusChoices.COMPLETED,
            priority=self.priority,
            category=self.category,
        )
        Note.objects.create(task=upcoming, content="Remember this")
        SubTask.objects.create(title="One step", parent_task=upcoming)

        response = self.client.get(reverse("dashboard"))

        self.assertEqual(response.context["task_count"], 5)
        self.assertEqual(response.context["note_count"], 1)
        self.assertEqual(response.context["subtask_count"], 1)
        self.assertIn(overdue, response.context["overdue_tasks"])
        self.assertIn(upcoming, response.context["upcoming_tasks"])
        self.assertNotIn(completed_late, response.context["overdue_tasks"])
        self.assertLessEqual(len(response.context["recent_tasks"]), 5)

    def test_dashboard_is_safe_with_an_empty_database(self):
        Task.objects.all().delete()
        Priority.objects.all().delete()
        Category.objects.all().delete()

        response = self.client.get(reverse("dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["task_count"], 0)
        self.assertEqual(list(response.context["overdue_tasks"]), [])
        self.assertEqual(list(response.context["upcoming_tasks"]), [])

    def test_task_detail_includes_related_notes_and_subtasks(self):
        task = Task.objects.get(title="Write database report")
        note = Note.objects.create(task=task, content="Check citations")
        subtask = SubTask.objects.create(title="Create ERD", parent_task=task)

        response = self.client.get(reverse("task-detail", args=(task.pk,)))

        self.assertEqual(response.context["task"], task)
        self.assertIn(note, response.context["task"].notes.all())
        self.assertIn(subtask, response.context["task"].subtasks.all())

    def test_valid_create_flows_cover_all_five_models(self):
        priority_response = self.client.post(reverse("priority-add"), {"name": "medium"})
        category_response = self.client.post(reverse("category-add"), {"name": "Work"})
        self.assertRedirects(priority_response, reverse("priority-list"))
        self.assertRedirects(category_response, reverse("category-list"))

        task_response = self.client.post(reverse("task-add"), self.task_payload())
        created_task = Task.objects.get(title="Prepare Hangarin presentation")
        self.assertRedirects(task_response, reverse("task-detail", args=(created_task.pk,)))

        note_response = self.client.post(
            reverse("note-add"),
            {"task": created_task.pk, "content": "Practice the demo"},
        )
        subtask_response = self.client.post(
            reverse("subtask-add"),
            {
                "title": "Open the dashboard",
                "status": StatusChoices.PENDING,
                "parent_task": created_task.pk,
            },
        )
        self.assertRedirects(note_response, reverse("note-list"))
        self.assertRedirects(subtask_response, reverse("subtask-list"))
        self.assertTrue(Note.objects.filter(content="Practice the demo").exists())
        self.assertTrue(SubTask.objects.filter(title="Open the dashboard").exists())

    def test_update_flows_cover_all_five_models(self):
        task = Task.objects.get(title="Write database report")
        note = Note.objects.create(task=task, content="Old note")
        subtask = SubTask.objects.create(title="Old step", parent_task=task)

        self.assertRedirects(
            self.client.post(reverse("priority-edit", args=(self.priority.pk,)), {"name": "medium"}),
            reverse("priority-list"),
        )
        self.assertRedirects(
            self.client.post(reverse("category-edit", args=(self.category.pk,)), {"name": "Work"}),
            reverse("category-list"),
        )
        self.assertRedirects(
            self.client.post(
                reverse("task-edit", args=(task.pk,)),
                self.task_payload(title="Updated report"),
            ),
            reverse("task-detail", args=(task.pk,)),
        )
        self.assertRedirects(
            self.client.post(
                reverse("note-edit", args=(note.pk,)),
                {"task": task.pk, "content": "Updated note"},
            ),
            reverse("note-list"),
        )
        self.assertRedirects(
            self.client.post(
                reverse("subtask-edit", args=(subtask.pk,)),
                {
                    "title": "Updated step",
                    "status": StatusChoices.COMPLETED,
                    "parent_task": task.pk,
                },
            ),
            reverse("subtask-list"),
        )
        task.refresh_from_db()
        note.refresh_from_db()
        subtask.refresh_from_db()
        self.assertEqual(task.title, "Updated report")
        self.assertEqual(note.content, "Updated note")
        self.assertEqual(subtask.title, "Updated step")

    def test_invalid_forms_preserve_values_and_do_not_write(self):
        original_count = Task.objects.count()

        task_response = self.client.post(
            reverse("task-add"), self.task_payload(title="", description="Keep this value")
        )
        duplicate_response = self.client.post(
            reverse("priority-add"), {"name": self.priority.name}
        )

        self.assertEqual(task_response.status_code, 200)
        self.assertEqual(task_response.context["form"].data["description"], "Keep this value")
        self.assertIn("title", task_response.context["form"].errors)
        self.assertEqual(Task.objects.count(), original_count)
        self.assertEqual(duplicate_response.status_code, 200)
        self.assertIn("name", duplicate_response.context["form"].errors)

    def test_form_cancel_target_does_not_write_and_rejects_external_return(self):
        task_count = Task.objects.count()
        response = self.client.get(
            reverse("note-add"),
            {"next": "https://evil.example/phish"},
        )

        self.assertEqual(response.context["cancel_url"], reverse("note-list"))
        self.assertEqual(Task.objects.count(), task_count)

    def test_child_create_can_return_to_its_task_detail(self):
        task = Task.objects.get(title="Write database report")
        return_url = reverse("task-detail", args=(task.pk,))

        response = self.client.post(
            f'{reverse("note-add")}?next={return_url}',
            {"task": task.pk, "content": "Return to parent", "next": return_url},
        )

        self.assertRedirects(response, return_url)

    def test_stale_object_urls_return_not_found(self):
        urls = (
            reverse("task-detail", args=(999999,)),
            reverse("task-edit", args=(999999,)),
            reverse("task-delete", args=(999999,)),
            reverse("priority-edit", args=(999999,)),
            reverse("category-delete", args=(999999,)),
            reverse("note-edit", args=(999999,)),
            reverse("subtask-delete", args=(999999,)),
        )
        for url in urls:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 404)

    def test_task_delete_get_reports_children_and_post_cascades(self):
        task = Task.objects.get(title="Write database report")
        note = Note.objects.create(task=task, content="Will be deleted")
        subtask = SubTask.objects.create(title="Will be deleted", parent_task=task)
        delete_url = reverse("task-delete", args=(task.pk,))

        get_response = self.client.get(delete_url)
        self.assertEqual(get_response.context["note_count"], 1)
        self.assertEqual(get_response.context["subtask_count"], 1)
        self.assertTrue(Task.objects.filter(pk=task.pk).exists())

        post_response = self.client.post(delete_url)
        self.assertRedirects(post_response, reverse("task-list"))
        self.assertFalse(Task.objects.filter(pk=task.pk).exists())
        self.assertFalse(Note.objects.filter(pk=note.pk).exists())
        self.assertFalse(SubTask.objects.filter(pk=subtask.pk).exists())

    def test_referenced_lookup_delete_is_friendly_and_non_destructive(self):
        task_ids = set(Task.objects.values_list("pk", flat=True))

        response = self.client.post(reverse("priority-delete", args=(self.priority.pk,)))

        self.assertEqual(response.status_code, 409)
        self.assertTrue(Priority.objects.filter(pk=self.priority.pk).exists())
        self.assertEqual(set(Task.objects.values_list("pk", flat=True)), task_ids)
        self.assertTrue(response.context["blocked"])
        self.assertIn("in use", " ".join(str(message) for message in get_messages(response.wsgi_request)))

    def test_unreferenced_lookup_rows_can_be_deleted(self):
        priority = Priority.objects.create(name="optional")
        category = Category.objects.create(name="Personal")

        priority_response = self.client.post(
            reverse("priority-delete", args=(priority.pk,))
        )
        category_response = self.client.post(
            reverse("category-delete", args=(category.pk,))
        )

        self.assertRedirects(priority_response, reverse("priority-list"))
        self.assertRedirects(category_response, reverse("category-list"))
        self.assertFalse(Priority.objects.filter(pk=priority.pk).exists())
        self.assertFalse(Category.objects.filter(pk=category.pk).exists())

    def test_child_deletes_can_return_to_parent_task(self):
        task = Task.objects.get(title="Write database report")
        note = Note.objects.create(task=task, content="Remove note")
        subtask = SubTask.objects.create(title="Remove step", parent_task=task)
        return_url = reverse("task-detail", args=(task.pk,))

        note_response = self.client.post(
            reverse("note-delete", args=(note.pk,)), {"next": return_url}
        )
        subtask_response = self.client.post(
            reverse("subtask-delete", args=(subtask.pk,)), {"next": return_url}
        )

        self.assertRedirects(note_response, return_url)
        self.assertRedirects(subtask_response, return_url)
        self.assertTrue(Task.objects.filter(pk=task.pk).exists())

    def test_get_requests_never_delete_records(self):
        task = Task.objects.get(title="Write database report")
        note = Note.objects.create(task=task, content="Keep me")

        response = self.client.get(reverse("note-delete", args=(note.pk,)))

        self.assertEqual(response.status_code, 200)
        self.assertTrue(Note.objects.filter(pk=note.pk).exists())
