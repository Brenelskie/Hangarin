from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import GroupAdmin, UserAdmin
from django.contrib.auth.models import Group

from allauth.account.admin import EmailAddressAdmin
from allauth.account.models import EmailAddress
from allauth.socialaccount.admin import SocialAccountAdmin
from allauth.socialaccount.models import SocialAccount, SocialApp, SocialToken

from .models import Category, Note, Priority, SubTask, Task


class SuperuserOnlyPrivilegeAdminMixin:
    """Reserve account and role administration for active superusers."""

    def has_module_permission(self, request):
        return request.user.is_superuser and super().has_module_permission(request)

    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser and super().has_view_permission(request, obj)

    def has_add_permission(self, request):
        return request.user.is_superuser and super().has_add_permission(request)

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser and super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser and super().has_delete_permission(request, obj)


class SuperuserOnlyUserAdmin(SuperuserOnlyPrivilegeAdminMixin, UserAdmin):
    pass


class SuperuserOnlyGroupAdmin(SuperuserOnlyPrivilegeAdminMixin, GroupAdmin):
    pass


class SuperuserOnlyEmailAddressAdmin(
    SuperuserOnlyPrivilegeAdminMixin,
    EmailAddressAdmin,
):
    pass


class SuperuserOnlySocialAccountAdmin(
    SuperuserOnlyPrivilegeAdminMixin,
    SocialAccountAdmin,
):
    pass


user_model = get_user_model()
if admin.site.is_registered(user_model):
    admin.site.unregister(user_model)
admin.site.register(user_model, SuperuserOnlyUserAdmin)

if admin.site.is_registered(Group):
    admin.site.unregister(Group)
admin.site.register(Group, SuperuserOnlyGroupAdmin)

if admin.site.is_registered(EmailAddress):
    admin.site.unregister(EmailAddress)
admin.site.register(EmailAddress, SuperuserOnlyEmailAddressAdmin)

if admin.site.is_registered(SocialAccount):
    admin.site.unregister(SocialAccount)
admin.site.register(SocialAccount, SuperuserOnlySocialAccountAdmin)

for credential_model in (SocialApp, SocialToken):
    if admin.site.is_registered(credential_model):
        admin.site.unregister(credential_model)


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ("title", "status", "deadline", "priority", "category")
    list_filter = ("status", "priority", "category")
    search_fields = ("title", "description")
    list_select_related = ("priority", "category")


@admin.register(SubTask)
class SubTaskAdmin(admin.ModelAdmin):
    list_display = ("title", "status", "parent_task_name")
    list_filter = ("status",)
    search_fields = ("title",)
    list_select_related = ("parent_task",)

    @admin.display(description="Parent Task", ordering="parent_task__title")
    def parent_task_name(self, obj):
        return obj.parent_task.title


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name",)
    search_fields = ("name",)


@admin.register(Priority)
class PriorityAdmin(admin.ModelAdmin):
    list_display = ("name",)
    search_fields = ("name",)


@admin.register(Note)
class NoteAdmin(admin.ModelAdmin):
    list_display = ("task", "content", "created_at")
    list_filter = ("created_at",)
    search_fields = ("content",)
    list_select_related = ("task",)
