from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter


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
        saved_user = super().save_user(request, user, form, commit=commit)
        clear_privileges(saved_user)
        if commit:
            saved_user.save(update_fields=("is_staff", "is_superuser"))
        return saved_user


class HangarinSocialAccountAdapter(DefaultSocialAccountAdapter):
    def new_user(self, request, sociallogin):
        return clear_privileges(super().new_user(request, sociallogin))

    def populate_user(self, request, sociallogin, data):
        return clear_privileges(super().populate_user(request, sociallogin, data))

    def save_user(self, request, sociallogin, form=None):
        clear_privileges(sociallogin.user)
        user = super().save_user(request, sociallogin, form=form)
        clear_privileges(user)
        user.save(update_fields=("is_staff", "is_superuser"))
        return user

    def list_apps(self, request, provider=None, client_id=None):
        """Use environment-backed settings apps, never database credentials."""
        apps = super().list_apps(
            request,
            provider=provider,
            client_id=client_id,
        )
        return [app for app in apps if app.pk is None]
