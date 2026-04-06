from django.shortcuts import get_object_or_404, redirect, render

from .models import GameSession, Puzzle, QuestionLog
from .services import classify_question


def _get_hint_data(game_session):
    hints = [
        game_session.puzzle.hint1,
        game_session.puzzle.hint2,
        game_session.puzzle.hint3,
    ]
    revealed_hints = [hint for hint in hints[: game_session.hint_used_count] if hint]
    remaining_hint_count = max(0, 3 - game_session.hint_used_count)

    hint_message = ""
    if game_session.hint_used_count >= 3:
        hint_message = "모든 힌트를 이미 사용했습니다."
    else:
        next_index = game_session.hint_used_count
        if next_index < len(hints) and not hints[next_index]:
            hint_message = "다음으로 공개할 힌트가 없습니다."

    return revealed_hints, remaining_hint_count, hint_message


def home(request):
    puzzles = Puzzle.objects.filter(is_active=True)
    return render(request, "game/home.html", {"puzzles": puzzles})


def start_game(request, puzzle_id):
    puzzle = get_object_or_404(Puzzle, id=puzzle_id, is_active=True)

    if not request.session.session_key:
        request.session.create()

    game_session = GameSession.objects.create(
        puzzle=puzzle,
        user=request.user if request.user.is_authenticated else None,
        session_key=request.session.session_key or "",
        status=GameSession.STATUS_PLAYING,
    )
    return redirect("game:play", game_id=game_session.id)


def play_view(request, game_id):
    game_session = get_object_or_404(GameSession.objects.select_related("puzzle"), id=game_id)
    question_logs = game_session.question_logs.all()
    revealed_hints, remaining_hint_count, hint_message = _get_hint_data(game_session)
    return render(
        request,
        "game/play.html",
        {
            "game_session": game_session,
            "puzzle": game_session.puzzle,
            "question_logs": question_logs,
            "revealed_hints": revealed_hints,
            "remaining_hint_count": remaining_hint_count,
            "hint_message": hint_message,
        },
    )


def ask_question(request, game_id):
    game_session = get_object_or_404(GameSession.objects.select_related("puzzle"), id=game_id)

    if request.method == "POST":
        question_text = request.POST.get("question_text", "").strip()
        if question_text:
            answer_label = classify_question(
                scenario=game_session.puzzle.scenario,
                answer_text=game_session.puzzle.answer_text,
                question_text=question_text,
            )
            QuestionLog.objects.create(
                game_session=game_session,
                question_text=question_text,
                answer_label=answer_label,
            )

    return redirect("game:play", game_id=game_session.id)


def use_hint(request, game_id):
    game_session = get_object_or_404(GameSession.objects.select_related("puzzle"), id=game_id)

    if request.method == "POST" and game_session.hint_used_count < 3:
        hints = [
            game_session.puzzle.hint1,
            game_session.puzzle.hint2,
            game_session.puzzle.hint3,
        ]
        next_index = game_session.hint_used_count
        if next_index < len(hints) and hints[next_index]:
            game_session.hint_used_count += 1
            game_session.save(update_fields=["hint_used_count"])

    return redirect("game:play", game_id=game_session.id)
