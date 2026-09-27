"""Authentication forms that preserve Hangarin's username-only local accounts."""

from allauth.account.utils import filter_users_by_email
from allauth.socialaccount.forms import SignupForm
from django import forms


class HangarinSocialSignupForm(SignupForm):
    """Allow a provider signup to complete without adding a local email field."""

    def _get_signup_fields(self, kwargs):
        # django-allauth always passes this keyword from its social form, even
        # when email is optional. Hangarin intentionally has no local email
        # signup field, so let the base form use the configured username fields.
        kwargs.pop("email_required", None)
        return super()._get_signup_fields(kwargs)

    def clean(self):
        cleaned_data = super().clean()
        emails = {
            address.email
            for address in self.sociallogin.email_addresses
            if address.email
        }
        if self.sociallogin.user.email:
            emails.add(self.sociallogin.user.email)

        if any(filter_users_by_email(email) for email in emails):
            raise forms.ValidationError(
                "That email already belongs to a Hangarin account. Sign in "
                "using the method that created the original account."
            )
        return cleaned_data
