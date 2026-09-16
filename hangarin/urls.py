"""
URL configuration for hangarin project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import include, path, re_path
from django.views.generic import TemplateView

from hangarin import account_views


unavailable_account_feature = TemplateView.as_view(
    template_name="account/feature_unavailable.html"
)

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/google/login/", account_views.google_login),
    path("accounts/github/login/", account_views.github_login),
    path(
        "accounts/email/",
        unavailable_account_feature,
        {
            "feature_title": "Email management is not available",
            "feature_message": (
                "Hangarin currently uses username-based accounts and does not "
                "send verification email. Ask a Hangarin administrator if your "
                "account details need to change."
            ),
        },
    ),
    path(
        "accounts/confirm-email/",
        unavailable_account_feature,
        {
            "feature_title": "Email verification is not available",
            "feature_message": (
                "Hangarin does not use email verification. You can continue with "
                "your username and the sign-in method used to create your account."
            ),
        },
    ),
    re_path(
        r"^accounts/confirm-email/[-:\w]+/$",
        unavailable_account_feature,
        {
            "feature_title": "Email verification is not available",
            "feature_message": (
                "Hangarin does not use email verification. You can continue with "
                "your username and the sign-in method used to create your account."
            ),
        },
    ),
    path(
        "accounts/password/reset/",
        unavailable_account_feature,
        {
            "feature_title": "Password recovery is not available",
            "feature_message": (
                "Hangarin does not send password-reset email yet. Ask a Hangarin "
                "administrator to help restore access to your account."
            ),
        },
    ),
    path(
        "accounts/password/reset/done/",
        unavailable_account_feature,
        {
            "feature_title": "Password recovery is not available",
            "feature_message": (
                "Hangarin does not send password-reset email yet. Ask a Hangarin "
                "administrator to help restore access to your account."
            ),
        },
    ),
    path(
        "accounts/password/reset/key/done/",
        unavailable_account_feature,
        {
            "feature_title": "Password recovery is not available",
            "feature_message": (
                "Hangarin does not accept password-reset links yet. Ask a Hangarin "
                "administrator to help restore access to your account."
            ),
        },
    ),
    re_path(
        r"^accounts/password/reset/key/[0-9A-Za-z]+-.+/$",
        unavailable_account_feature,
        {
            "feature_title": "Password recovery is not available",
            "feature_message": (
                "Hangarin does not accept password-reset links yet. Ask a Hangarin "
                "administrator to help restore access to your account."
            ),
        },
    ),
    path(
        "accounts/3rdparty/",
        unavailable_account_feature,
        {
            "feature_title": "Account connections are not available",
            "feature_message": (
                "Hangarin cannot link or remove Google and GitHub identities after "
                "signup yet. Continue using the sign-in method that created your "
                "account."
            ),
        },
    ),
    path("accounts/", include("allauth.urls")),
    path("", include("tasks.urls")),
]
