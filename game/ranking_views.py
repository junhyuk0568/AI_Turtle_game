from django.shortcuts import get_object_or_404, render

from .models import Puzzle
from .rankings import overall_ranking, position_of, puzzle_ranking


RANKING_SIZE = 50


def _board(rows, is_mine):
    """Top rows plus the viewer's own entry when it falls below the board."""
    entries = [{"rank": rank, "row": row, "mine": is_mine(row)} for rank, row in enumerate(rows, start=1)]
    mine = next((entry for entry in entries if entry["mine"]), None)
    top = entries[:RANKING_SIZE]
    return top, (mine if mine and mine["rank"] > RANKING_SIZE else None)


def _context(request, **extra):
    return {"puzzles": Puzzle.objects.filter(is_active=True), **extra}


def ranking_view(request):
    user_id = request.user.pk if request.user.is_authenticated else None
    top, mine_below = _board(overall_ranking(), lambda profile: profile.user_id == user_id)
    return render(request, "game/ranking.html", _context(request, entries=top, mine_below=mine_below, current=None))


def puzzle_ranking_view(request, puzzle_id):
    puzzle = get_object_or_404(Puzzle, id=puzzle_id, is_active=True)
    user_id = request.user.pk if request.user.is_authenticated else None
    top, mine_below = _board(puzzle_ranking(puzzle), lambda game: game.user_id == user_id)
    return render(request, "game/ranking.html", _context(request, entries=top, mine_below=mine_below, current=puzzle))


def game_rank(game_session):
    """Position of a ranked game on its puzzle board, or None."""
    if not game_session.is_ranked:
        return None
    return position_of(puzzle_ranking(game_session.puzzle), lambda game: game.pk == game_session.pk)
