from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render

from .models import GameSession, Puzzle, QuestionLog
from .services import FINAL_ANSWER_CORRECT, OpenAIServiceError, classify_final_answer, classify_question


HINT_FIELDS = ("hint1", "hint2", "hint3")
MAX_HINT_COUNT = len(HINT_FIELDS)
MAX_QUESTION_LENGTH = 500
MAX_ANSWER_LENGTH = 2000


def _get_game_session(game_id):
    return get_object_or_404(GameSession.objects.select_related("puzzle"), id=game_id)


def _redirect_if_cleared(game_session):
    if game_session.status == GameSession.STATUS_CLEARED:
        return redirect("game:result", game_id=game_session.id)
    return None


def _get_hints(puzzle):
    return [getattr(puzzle, field) for field in HINT_FIELDS]


def _get_hint_data(game_session):
    hints = _get_hints(game_session.puzzle)
    revealed_hints = [hint for hint in hints[: game_session.hint_used_count] if hint]
    remaining_hint_count = max(0, MAX_HINT_COUNT - game_session.hint_used_count)

    hint_message = ""
    if game_session.hint_used_count >= MAX_HINT_COUNT:
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
    game_session = _get_game_session(game_id)
    cleared_response = _redirect_if_cleared(game_session)
    if cleared_response:
        return cleared_response

    question_logs = game_session.question_logs.order_by("created_at")
    revealed_hints, remaining_hint_count, hint_message = _get_hint_data(game_session)
    final_answer_feedback = request.session.pop(f"final_answer_feedback_{game_session.id}", None)
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
            "final_answer_feedback": final_answer_feedback,
        },
    )


def ask_question(request, game_id):
    game_session = _get_game_session(game_id)
    cleared_response = _redirect_if_cleared(game_session)
    if cleared_response:
        return cleared_response

    if request.method == "POST":
        question_text = request.POST.get("question_text", "").strip()
        if len(question_text) > MAX_QUESTION_LENGTH:
            messages.error(request, f"질문은 {MAX_QUESTION_LENGTH}자 이하로 입력해주세요.")
        elif game_session.question_logs.filter(question_text=question_text).exists():
            messages.warning(request, "이미 같은 질문을 했습니다.")
        elif question_text:
            try:
                answer_label = classify_question(
                    scenario=game_session.puzzle.scenario,
                    answer_text=game_session.puzzle.answer_text,
                    question_criteria=game_session.puzzle.get_question_criteria(),
                    question_text=question_text,
                )
            except OpenAIServiceError as exc:
                messages.error(request, str(exc))
                return redirect("game:play", game_id=game_session.id)

            QuestionLog.objects.create(
                game_session=game_session,
                question_text=question_text,
                answer_label=answer_label,
            )

    return redirect("game:play", game_id=game_session.id)


def use_hint(request, game_id):
    game_session = _get_game_session(game_id)
    cleared_response = _redirect_if_cleared(game_session)
    if cleared_response:
        return cleared_response

    if request.method == "POST" and game_session.hint_used_count < MAX_HINT_COUNT:
        hints = _get_hints(game_session.puzzle)
        next_index = game_session.hint_used_count
        if next_index < len(hints) and hints[next_index]:
            game_session.hint_used_count += 1
            game_session.save(update_fields=["hint_used_count"])

    return redirect("game:play", game_id=game_session.id)


def submit_final_answer(request, game_id):
    game_session = _get_game_session(game_id)
    cleared_response = _redirect_if_cleared(game_session)
    if cleared_response:
        return cleared_response

    if request.method == "POST":
        submitted_answer = request.POST.get("submitted_answer", "").strip()
        if len(submitted_answer) > MAX_ANSWER_LENGTH:
            messages.error(request, f"정답은 {MAX_ANSWER_LENGTH}자 이하로 입력해주세요.")
            return redirect("game:play", game_id=game_session.id)

        try:
            result_label = classify_final_answer(
                scenario=game_session.puzzle.scenario,
                answer_text=game_session.puzzle.answer_text,
                answer_checkpoints=game_session.puzzle.get_answer_checkpoints(),
                submitted_answer=submitted_answer,
            )
        except OpenAIServiceError as exc:
            messages.error(request, str(exc))
            return redirect("game:play", game_id=game_session.id)

        if result_label == FINAL_ANSWER_CORRECT:
            game_session.mark_cleared(submitted_answer)
            return redirect("game:result", game_id=game_session.id)

        request.session[f"final_answer_feedback_{game_session.id}"] = {
            "label": result_label,
            "submitted_answer": submitted_answer,
        }

    return redirect("game:play", game_id=game_session.id)


def result_view(request, game_id):
    game_session = _get_game_session(game_id)
    if game_session.status != GameSession.STATUS_CLEARED:
        return redirect("game:play", game_id=game_session.id)

    question_count = game_session.question_logs.count()
    return render(
        request,
        "game/result.html",
        {
            "game_session": game_session,
            "puzzle": game_session.puzzle,
            "question_count": question_count,
        },
    )
