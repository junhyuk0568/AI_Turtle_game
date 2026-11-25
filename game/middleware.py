from urllib.parse import quote

from django.http import JsonResponse
from django.shortcuts import redirect
from django.urls import reverse

from .models import PlayerProfile

EXEMPT_PREFIXES = ("/accounts/", "/admin/", "/static/", "/me/", "/privacy/")


class NicknameRequiredMiddleware:
    """Send logged-in players without a nickname to the nickname page first."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        if (
            user is not None
            and user.is_authenticated
            and not user.is_staff
            and not request.path.startswith(EXEMPT_PREFIXES)
            and not PlayerProfile.objects.filter(user=user).exists()
        ):
            url = f"{reverse('game:nickname')}?next={quote(request.get_full_path())}"
            if "application/json" in request.headers.get("Accept", ""):
                return JsonResponse({"ok": False, "message": "닉네임을 먼저 정해 주세요.", "redirect": url})
            return redirect(url)
        return self.get_response(request)
