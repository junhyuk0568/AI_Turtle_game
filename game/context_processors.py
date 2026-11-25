from django.conf import settings


def account_flags(request):
    return {"google_login_enabled": settings.GOOGLE_LOGIN_ENABLED}
