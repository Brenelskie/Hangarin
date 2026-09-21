"""Authentication forms that preserve Hangarin's username-only local accounts."""

from allauth.socialaccount.forms import SignupForm


class HangarinSocialSignupForm(SignupForm):
    """Allow a provider signup to complete without adding a local email field."""

    def _get_signup_fields(self, kwargs):
        # django-allauth always passes this keyword from its social form, even
        # when email is optional. Hangarin intentionally has no local email
        # signup field, so let the base form use the configured username fields.
        kwargs.pop("email_required", None)
        return super()._get_signup_fields(kwargs)
