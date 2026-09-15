from urllib.parse import urlencode, urlsplit

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LogoutView
from django.core.exceptions import ImproperlyConfigured
from django.core.paginator import InvalidPage
from django.db.models import Count, Q
from django.db.models.deletion import ProtectedError
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    ListView,
    TemplateView,
    UpdateView,
)

from .forms import CategoryForm, NoteForm, PriorityForm, SubTaskForm, TaskForm
from .models import Category, Note, Priority, StatusChoices, SubTask, Task


SEARCH_LIMIT = 100
PAGE_SIZE = 10
SAFE_RETURN_PREFIXES = (
    "/tasks/",
    "/priorities/",
    "/categories/",
    "/notes/",
    "/subtasks/",
)


def safe_return_url(request, fallback):
    candidate = request.POST.get("next") or request.GET.get("next")
    if not candidate:
        return fallback
    if not url_has_allowed_host_and_scheme(
        candidate,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return fallback
    path = urlsplit(candidate).path
    if path != "/" and not path.startswith(SAFE_RETURN_PREFIXES):
        return fallback
    return candidate


class ProtectedLogoutView(LoginRequiredMixin, LogoutView):
    http_method_names = ("post", "options")


class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = "tasks/dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        now = timezone.now()
        incomplete = ~Q(status=StatusChoices.COMPLETED)
        context.update(
            {
                "task_count": Task.objects.count(),
                "pending_count": Task.objects.filter(status=StatusChoices.PENDING).count(),
                "in_progress_count": Task.objects.filter(
                    status=StatusChoices.IN_PROGRESS
                ).count(),
                "completed_count": Task.objects.filter(
                    status=StatusChoices.COMPLETED
                ).count(),
                "priority_count": Priority.objects.count(),
                "category_count": Category.objects.count(),
                "note_count": Note.objects.count(),
                "subtask_count": SubTask.objects.count(),
                "overdue_tasks": Task.objects.select_related("priority", "category")
                .filter(incomplete, deadline__lt=now)
                .order_by("deadline", "id")[:5],
                "upcoming_tasks": Task.objects.select_related("priority", "category")
                .filter(incomplete, deadline__gte=now)
                .order_by("deadline", "id")[:5],
                "recent_tasks": Task.objects.select_related("priority", "category")
                .order_by("-updated_at", "-id")[:5],
            }
        )
        return context


class SafeQueryListView(LoginRequiredMixin, ListView):
    paginate_by = PAGE_SIZE
    search_fields = ()
    filter_fields = {}
    ordering_map = {}
    default_ordering = ("id",)

    def validated_parameters(self):
        if hasattr(self, "_validated_parameters"):
            return self._validated_parameters

        params = {}
        query = self.request.GET.get("q", "").strip()[:SEARCH_LIMIT]
        if query:
            params["q"] = query

        for parameter, validator in self.filter_fields.items():
            value = self.request.GET.get(parameter, "").strip()
            if value and validator(value):
                params[parameter] = value

        ordering = self.request.GET.get("order", "").strip()
        if ordering in self.ordering_map:
            params["order"] = ordering

        self._validated_parameters = params
        return params

    def get_queryset(self):
        queryset = super().get_queryset()
        params = self.validated_parameters()
        query = params.get("q")
        if query and self.search_fields:
            search = Q()
            for field in self.search_fields:
                search |= Q(**{f"{field}__icontains": query})
            queryset = queryset.filter(search)

        for parameter in self.filter_fields:
            if parameter in params:
                queryset = self.apply_filter(queryset, parameter, params[parameter])

        ordering = self.ordering_map.get(params.get("order"), self.default_ordering)
        return queryset.order_by(*ordering)

    def apply_filter(self, queryset, parameter, value):
        return queryset.filter(**{parameter: value})

    def paginate_queryset(self, queryset, page_size):
        paginator = self.get_paginator(
            queryset,
            page_size,
            orphans=self.get_paginate_orphans(),
            allow_empty_first_page=self.get_allow_empty(),
        )
        page_kwarg = self.page_kwarg
        page_number = self.kwargs.get(page_kwarg) or self.request.GET.get(page_kwarg) or 1
        try:
            page = paginator.page(page_number)
        except InvalidPage:
            page = paginator.page(1)
        return paginator, page, page.object_list, page.has_other_pages()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        params = self.validated_parameters()
        context.update(
            {
                "active_query": params,
                "query_string": urlencode(params),
                "database_empty": not self.model.objects.exists(),
                "filtered_empty": bool(params) and not context["object_list"],
            }
        )
        return context


def valid_status(value):
    return value in StatusChoices.values


def valid_priority(value):
    return value.isdigit() and Priority.objects.filter(pk=value).exists()


def valid_category(value):
    return value.isdigit() and Category.objects.filter(pk=value).exists()


def valid_task(value):
    return value.isdigit() and Task.objects.filter(pk=value).exists()


class TaskListView(SafeQueryListView):
    model = Task
    template_name = "tasks/task_list.html"
    context_object_name = "tasks"
    search_fields = ("title", "description")
    filter_fields = {
        "status": valid_status,
        "priority": valid_priority,
        "category": valid_category,
    }
    ordering_map = {
        "title": ("title", "id"),
        "-title": ("-title", "id"),
        "deadline": ("deadline", "id"),
        "-deadline": ("-deadline", "id"),
        "status": ("status", "id"),
        "-status": ("-status", "id"),
    }
    default_ordering = ("deadline", "id")

    def get_queryset(self):
        return super().get_queryset().select_related("priority", "category")

    def apply_filter(self, queryset, parameter, value):
        if parameter in {"priority", "category"}:
            return queryset.filter(**{f"{parameter}_id": value})
        return super().apply_filter(queryset, parameter, value)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["priorities"] = Priority.objects.all()
        context["categories"] = Category.objects.all()
        context["statuses"] = StatusChoices.choices
        return context


class PriorityListView(SafeQueryListView):
    model = Priority
    template_name = "tasks/priority_list.html"
    context_object_name = "priorities"
    search_fields = ("name",)
    ordering_map = {"name": ("name", "id"), "-name": ("-name", "id")}
    default_ordering = ("name", "id")


class CategoryListView(SafeQueryListView):
    model = Category
    template_name = "tasks/category_list.html"
    context_object_name = "categories"
    search_fields = ("name",)
    ordering_map = {"name": ("name", "id"), "-name": ("-name", "id")}
    default_ordering = ("name", "id")


class NoteListView(SafeQueryListView):
    model = Note
    template_name = "tasks/note_list.html"
    context_object_name = "notes"
    search_fields = ("content", "task__title")
    filter_fields = {"task": valid_task}
    ordering_map = {
        "created": ("created_at", "id"),
        "-created": ("-created_at", "id"),
        "task": ("task__title", "id"),
    }
    default_ordering = ("-created_at", "-id")

    def get_queryset(self):
        return super().get_queryset().select_related("task")

    def apply_filter(self, queryset, parameter, value):
        return queryset.filter(task_id=value)


class SubTaskListView(SafeQueryListView):
    model = SubTask
    template_name = "tasks/subtask_list.html"
    context_object_name = "subtasks"
    search_fields = ("title", "parent_task__title")
    filter_fields = {"status": valid_status, "task": valid_task}
    ordering_map = {
        "title": ("title", "id"),
        "-title": ("-title", "id"),
        "status": ("status", "id"),
        "task": ("parent_task__title", "id"),
    }
    default_ordering = ("created_at", "id")

    def get_queryset(self):
        return super().get_queryset().select_related("parent_task")

    def apply_filter(self, queryset, parameter, value):
        if parameter == "task":
            return queryset.filter(parent_task_id=value)
        return super().apply_filter(queryset, parameter, value)


class TaskDetailView(LoginRequiredMixin, DetailView):
    model = Task
    template_name = "tasks/task_detail.html"
    context_object_name = "task"

    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .select_related("priority", "category")
            .prefetch_related("notes", "subtasks")
        )


class EntityFormMixin(LoginRequiredMixin):
    template_name = "tasks/entity_form.html"
    entity_label = "record"
    default_success_url = None

    def get_fallback_url(self):
        if self.default_success_url is None:
            raise ImproperlyConfigured("default_success_url is required")
        return reverse(self.default_success_url)

    def get_success_url(self):
        return safe_return_url(self.request, self.get_fallback_url())

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f"{self.entity_label} saved successfully.")
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "entity_label": self.entity_label,
                "cancel_url": safe_return_url(self.request, self.get_fallback_url()),
                "return_url": safe_return_url(self.request, ""),
            }
        )
        return context


class TaskFormMixin(EntityFormMixin):
    model = Task
    form_class = TaskForm
    entity_label = "Task"

    def get_fallback_url(self):
        if getattr(self, "object", None) and self.object.pk:
            return reverse("task-detail", args=(self.object.pk,))
        return reverse("task-list")

    def get_success_url(self):
        return reverse("task-detail", args=(self.object.pk,))


class TaskCreateView(TaskFormMixin, CreateView):
    pass


class TaskUpdateView(TaskFormMixin, UpdateView):
    pass


class PriorityCreateView(EntityFormMixin, CreateView):
    model = Priority
    form_class = PriorityForm
    entity_label = "Priority"
    default_success_url = "priority-list"


class PriorityUpdateView(EntityFormMixin, UpdateView):
    model = Priority
    form_class = PriorityForm
    entity_label = "Priority"
    default_success_url = "priority-list"


class CategoryCreateView(EntityFormMixin, CreateView):
    model = Category
    form_class = CategoryForm
    entity_label = "Category"
    default_success_url = "category-list"


class CategoryUpdateView(EntityFormMixin, UpdateView):
    model = Category
    form_class = CategoryForm
    entity_label = "Category"
    default_success_url = "category-list"


class NoteCreateView(EntityFormMixin, CreateView):
    model = Note
    form_class = NoteForm
    entity_label = "Note"
    default_success_url = "note-list"


class NoteUpdateView(EntityFormMixin, UpdateView):
    model = Note
    form_class = NoteForm
    entity_label = "Note"
    default_success_url = "note-list"


class SubTaskCreateView(EntityFormMixin, CreateView):
    model = SubTask
    form_class = SubTaskForm
    entity_label = "Subtask"
    default_success_url = "subtask-list"


class SubTaskUpdateView(EntityFormMixin, UpdateView):
    model = SubTask
    form_class = SubTaskForm
    entity_label = "Subtask"
    default_success_url = "subtask-list"


class EntityDeleteView(LoginRequiredMixin, DeleteView):
    template_name = "tasks/confirm_delete.html"
    entity_label = "record"
    default_success_url = None

    def get_fallback_url(self):
        return reverse(self.default_success_url)

    def get_success_url(self):
        return safe_return_url(self.request, self.get_fallback_url())

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "entity_label": self.entity_label,
                "cancel_url": safe_return_url(self.request, self.get_fallback_url()),
                "return_url": safe_return_url(self.request, ""),
            }
        )
        return context

    def form_valid(self, form):
        success_url = self.get_success_url()
        try:
            self.object.delete()
        except ProtectedError:
            messages.error(
                self.request,
                f"This {self.entity_label.lower()} is in use and cannot be deleted.",
            )
            context = self.get_context_data(form=form, blocked=True)
            return self.render_to_response(context, status=409)
        messages.success(self.request, f"{self.entity_label} deleted successfully.")
        return HttpResponseRedirect(success_url)


class TaskDeleteView(EntityDeleteView):
    model = Task
    entity_label = "Task"
    default_success_url = "task-list"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["note_count"] = self.object.notes.count()
        context["subtask_count"] = self.object.subtasks.count()
        context["cascade_delete"] = True
        return context


class PriorityDeleteView(EntityDeleteView):
    model = Priority
    entity_label = "Priority"
    default_success_url = "priority-list"

    def get_queryset(self):
        return super().get_queryset().annotate(task_count=Count("tasks"))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["task_count"] = self.object.task_count
        context["protected_delete"] = True
        return context


class CategoryDeleteView(EntityDeleteView):
    model = Category
    entity_label = "Category"
    default_success_url = "category-list"

    def get_queryset(self):
        return super().get_queryset().annotate(task_count=Count("tasks"))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["task_count"] = self.object.task_count
        context["protected_delete"] = True
        return context


class NoteDeleteView(EntityDeleteView):
    model = Note
    entity_label = "Note"
    default_success_url = "note-list"


class SubTaskDeleteView(EntityDeleteView):
    model = SubTask
    entity_label = "Subtask"
    default_success_url = "subtask-list"
