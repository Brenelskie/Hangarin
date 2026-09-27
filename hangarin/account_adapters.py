from allauth.account.adapter import (
    DefaultAccountAdapter,
    get_adapter as get_account_adapter,
)
from allauth.account.utils import user_email, user_username
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.core.exceptions import ValidationError


def clear_privileges(user):
    """Public account flows always produce ordinary Hangarin users."""
    user.is_staff = False
    user.is_superuser = False
    return user


class HangarinAccountAdapter(DefaultAccountAdapter):
    def new_user(self, request):
        return clear_privileges(super().new_user(request))

    def save_user(self, request, user, form, commit=True):
        clear_privileges(user)
        return super().save_user(request, user, form, commit=commit)


class HangarinSocialAccountAdapter(DefaultSocialAccountAdapter):
    def new_user(self, request, sociallogin):
        return clear_privileges(super().new_user(request, sociallogin))

    def populate_user(self, request, sociallogin, data):
        return clear_privileges(super().populate_user(request, sociallogin, data))

    def save_user(self, request, sociallogin, form=None):
        clear_privileges(sociallogin.user)
        return super().save_user(request, sociallogin, form=form)

    def is_auto_signup_allowed(self, request, sociallogin):
        email = user_email(sociallogin.user)
        username = user_username(sociallogin.user)
        if not email or not username:
            return False
        try:
            get_account_adapter(request).clean_username(username)
        except ValidationError:
            return False
        return super().is_auto_signup_allowed(request, sociallogin)

    def list_apps(self, request, provider=None, client_id=None):
        """Use environment-backed settings apps, never database credentials."""
        apps = super().list_apps(
            request,
            provider=provider,
            client_id=client_id,
        )
        return [app for app in apps if app.pk is None]
