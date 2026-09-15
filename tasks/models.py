from django.db import models


class BaseModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True, db_index=True)

    class Meta:
        abstract = True


class StatusChoices(models.TextChoices):
    PENDING = "Pending", "Pending"
    IN_PROGRESS = "In Progress", "In Progress"
    COMPLETED = "Completed", "Completed"


class Priority(BaseModel):
    name = models.CharField(max_length=100, unique=True)

    class Meta:
        ordering = ("name", "id")
        verbose_name_plural = "Priorities"

    def __str__(self):
        return self.name


class Category(BaseModel):
    name = models.CharField(max_length=100, unique=True)

    class Meta:
        ordering = ("name", "id")
        verbose_name_plural = "Categories"

    def __str__(self):
        return self.name


class Task(BaseModel):
    title = models.CharField(max_length=255)
    description = models.TextField()
    deadline = models.DateTimeField()
    status = models.CharField(
        max_length=20,
        choices=StatusChoices.choices,
        default=StatusChoices.PENDING,
    )
    priority = models.ForeignKey(
        Priority,
        on_delete=models.PROTECT,
        related_name="tasks",
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name="tasks",
    )

    class Meta:
        ordering = ("deadline", "id")
        constraints = (
            models.CheckConstraint(
                condition=models.Q(status__in=StatusChoices.values),
                name="task_valid_status",
            ),
        )

    def __str__(self):
        return self.title


class Note(BaseModel):
    task = models.ForeignKey(
        Task,
        on_delete=models.CASCADE,
        related_name="notes",
    )
    content = models.TextField()

    class Meta:
        ordering = ("-created_at", "id")

    def __str__(self):
        excerpt = self.content[:40]
        if len(self.content) > 40:
            excerpt = f"{excerpt}…"
        return f"{self.task}: {excerpt}"


class SubTask(BaseModel):
    title = models.CharField(max_length=255)
    status = models.CharField(
        max_length=20,
        choices=StatusChoices.choices,
        default=StatusChoices.PENDING,
    )
    parent_task = models.ForeignKey(
        Task,
        on_delete=models.CASCADE,
        related_name="subtasks",
    )

    class Meta:
        ordering = ("created_at", "id")
        verbose_name = "Subtask"
        verbose_name_plural = "Subtasks"
        constraints = (
            models.CheckConstraint(
                condition=models.Q(status__in=StatusChoices.values),
                name="subtask_valid_status",
            ),
        )

    def __str__(self):
        return f"{self.title} — {self.parent_task.title}"
