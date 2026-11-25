"""Account helpers: moving guest games to a logged-in player."""
from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver

from .models import GameSession

GUEST_KEY_SESSION_NAME = "guest_session_key"


def remember_guest_key(request):
    """Store the anonymous session key inside the session.

    Django changes the session key when a user logs in, so the old key would be
    lost; the session data itself survives, which is where we keep it.
    """
    key = request.session.session_key
    if key and request.session.get(GUEST_KEY_SESSION_NAME) != key:
        request.session[GUEST_KEY_SESSION_NAME] = key


def claim_guest_games(user, guest_session_key):
    """Give the account every game that the guest session owned. Returns the count."""
    if not guest_session_key:
        return 0
    return GameSession.objects.filter(session_key=guest_session_key, user__isnull=True).update(user=user)


@receiver(user_logged_in)
def claim_guest_games_on_login(sender, request, user, **kwargs):
    if request is None or not hasattr(request, "session"):
        return
    guest_key = request.session.pop(GUEST_KEY_SESSION_NAME, None)
    claim_guest_games(user, guest_key)
