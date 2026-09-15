from django import forms

from .models import Category, Note, Priority, SubTask, Task


class TaskForm(forms.ModelForm):
    class Meta:
        model = Task
        fields = ("title", "description", "deadline", "status", "priority", "category")
        widgets = {
            "deadline": forms.DateTimeInput(
                attrs={"type": "datetime-local"},
                format="%Y-%m-%dT%H:%M",
            ),
            "description": forms.Textarea(attrs={"rows": 5}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["deadline"].input_formats = ("%Y-%m-%dT%H:%M",)


class PriorityForm(forms.ModelForm):
    class Meta:
        model = Priority
        fields = ("name",)


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ("name",)


class NoteForm(forms.ModelForm):
    class Meta:
        model = Note
        fields = ("task", "content")
        widgets = {"content": forms.Textarea(attrs={"rows": 5})}


class SubTaskForm(forms.ModelForm):
    class Meta:
        model = SubTask
        fields = ("title", "status", "parent_task")
