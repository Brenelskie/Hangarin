from allauth.socialaccount.providers.github.views import (
    oauth2_login as github_oauth2_login,
)
from allauth.socialaccount.providers.base.constants import AuthProcess
from allauth.socialaccount.providers.google.views import (
    oauth2_login as google_oauth2_login,
)
from allauth.utils import get_request_param
from django.contrib.auth.decorators import login_not_required
from django.shortcuts import render
from django.views.decorators.csrf import csrf_protect


def _provider_login_without_connections(request, provider_login):
    if get_request_param(request, "process") == AuthProcess.CONNECT:
        return render(
            request,
            "account/feature_unavailable.html",
            {
                "feature_title": "Account connections are not available",
                "feature_message": (
                    "Hangarin cannot link Google or GitHub identities to an existing "
                    "account yet. Continue using the sign-in method that created "
                    "your account."
                ),
            },
            status=403 if request.method == "POST" else 200,
        )
    return provider_login(request)


@login_not_required
@csrf_protect
def google_login(request):
    return _provider_login_without_connections(request, google_oauth2_login)


@login_not_required
@csrf_protect
def github_login(request):
    return _provider_login_without_connections(request, github_oauth2_login)
