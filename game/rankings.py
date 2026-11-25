"""Rankings: each account's FIRST clear of a puzzle is ranked; later clears are practice.

The truth is shown after a clear, so a replay would always score full marks.
Guest clears count once they move to an account at login (oldest clear first).
Only players with a nickname appear; Google names and emails are never used.
"""

from django.db import IntegrityError, transaction
from django.db.models import Count, Max, Sum

from .models import GameSession, PlayerProfile


PUZZLE_ORDER = ("-final_score", "play_seconds", "cleared_at", "id")


def assign_rank(game_session):
    """Rank a cleared game when it is its account's first clear of the puzzle."""
    if not game_session.user_id or game_session.status != GameSession.STATUS_CLEARED or game_session.is_ranked:
        return False
    already_ranked = GameSession.objects.filter(
        user_id=game_session.user_id, puzzle_id=game_session.puzzle_id, is_ranked=True
    ).exists()
    if already_ranked:
        return False
    try:
        with transaction.atomic():
            GameSession.objects.filter(pk=game_session.pk).update(is_ranked=True)
    except IntegrityError:
        # A parallel request ranked another clear of the same puzzle first.
        return False
    game_session.is_ranked = True
    return True


def rank_claimed_games(user):
    """After guest games move to an account, rank the oldest clear of each unranked puzzle."""
    cleared = GameSession.objects.filter(user=user, status=GameSession.STATUS_CLEARED).order_by("cleared_at", "id")
    for game_session in cleared:
        assign_rank(game_session)


def _ranked_games():
    return GameSession.objects.filter(
        is_ranked=True, puzzle__is_active=True, user__player_profile__isnull=False
    ).select_related("user__player_profile")


def puzzle_ranking(puzzle):
    """Ranked games of one puzzle in order: score, then faster clear, then earlier clear."""
    return list(_ranked_games().filter(puzzle=puzzle).order_by(*PUZZLE_ORDER))


def overall_ranking():
    """Players by the sum of their first-clear scores, then more puzzles, then who got there first."""
    return list(
        PlayerProfile.objects.filter(user__game_sessions__is_ranked=True, user__game_sessions__puzzle__is_active=True)
        .annotate(
            total_score=Sum("user__game_sessions__final_score"),
            cleared_count=Count("user__game_sessions"),
            last_cleared_at=Max("user__game_sessions__cleared_at"),
        )
        .order_by("-total_score", "-cleared_count", "last_cleared_at", "id")
    )


def position_of(rows, predicate):
    """1-based position of the first row matching predicate, or None."""
    for index, row in enumerate(rows, start=1):
        if predicate(row):
            return index
    return None
