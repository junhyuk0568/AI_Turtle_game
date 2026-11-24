from django.conf import settings
from django.contrib import messages
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .models import GameSession, Puzzle, QuestionLog
from .services import AIServiceError, FINAL_ANSWER_CORRECT, classify_final_answer, classify_question


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


def _get_fixed_hints(puzzle):
    return [getattr(puzzle, field) for field in HINT_FIELDS]


def _get_revealed_hints(game_session):
    if game_session.revealed_hint_texts:
        return list(game_session.revealed_hint_texts)
    # Sessions started before adaptive hints stored only the count of fixed hints.
    return [hint for hint in _get_fixed_hints(game_session.puzzle)[: game_session.hint_used_count] if hint]


def _pick_next_hint(game_session):
    """Prefer a hint for a checkpoint the player has not uncovered yet, then fixed hints."""
    puzzle = game_session.puzzle
    given = set(_get_revealed_hints(game_session))
    revealed_numbers = game_session.revealed_checkpoint_numbers()
    checkpoint_count = len(puzzle.get_answer_checkpoints())

    for number, hint in enumerate(puzzle.get_checkpoint_hints()[:checkpoint_count], start=1):
        if hint and number not in revealed_numbers and hint not in given:
            return hint

    for hint in _get_fixed_hints(puzzle):
        if hint and hint not in given:
            return hint
    return None


def _get_hint_data(game_session):
    revealed_hints = _get_revealed_hints(game_session)
    remaining_hint_count = max(0, MAX_HINT_COUNT - game_session.hint_used_count)

    hint_message = ""
    if game_session.hint_used_count >= MAX_HINT_COUNT:
        hint_message = "모든 힌트를 이미 사용했습니다."
    elif _pick_next_hint(game_session) is None:
        hint_message = "다음으로 공개할 힌트가 없습니다."

    return revealed_hints, remaining_hint_count, hint_message




def home(request):
    puzzles = Puzzle.objects.filter(is_active=True)
    active_games = []
    if request.user.is_authenticated:
        active_games = GameSession.objects.filter(
            user=request.user,
            status=GameSession.STATUS_PLAYING,
            puzzle__is_active=True,
        ).select_related("puzzle").annotate(question_count_value=Count("question_logs"))
    elif request.session.session_key:
        active_games = GameSession.objects.filter(
            session_key=request.session.session_key,
            status=GameSession.STATUS_PLAYING,
            puzzle__is_active=True,
        ).select_related("puzzle").annotate(question_count_value=Count("question_logs"))

    return render(request, "game/home.html", {"puzzles": puzzles, "active_games": active_games})


def start_game(request, puzzle_id):
    puzzle = get_object_or_404(Puzzle, id=puzzle_id, is_active=True)

    if not request.session.session_key:
        request.session.create()

    lookup = {
        "puzzle": puzzle,
        "status": GameSession.STATUS_PLAYING,
    }
    if request.user.is_authenticated:
        lookup["user"] = request.user
    else:
        lookup["session_key"] = request.session.session_key or ""

    game_session = GameSession.objects.filter(**lookup).first()
    if game_session is None:
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
            "required_keyword_count": len(game_session.puzzle.get_answer_checkpoints()),
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
            recent_logs = game_session.question_logs.order_by("-created_at")[: settings.QUESTION_HISTORY_LIMIT]
            history = [(log.question_text, log.answer_label) for log in reversed(list(recent_logs))]
            puzzle = game_session.puzzle
            try:
                judgement = classify_question(
                    scenario=puzzle.scenario,
                    answer_text=puzzle.answer_text,
                    question_criteria=puzzle.get_question_criteria(),
                    answer_checkpoints=puzzle.get_answer_checkpoints(),
                    question_text=question_text,
                    history=history,
                )
            except AIServiceError as exc:
                messages.error(request, str(exc))
                return redirect("game:play", game_id=game_session.id)

            QuestionLog.objects.create(
                game_session=game_session,
                question_text=question_text,
                answer_label=judgement.label,
                revealed_checkpoints=judgement.revealed_checkpoints,
            )

    return redirect("game:play", game_id=game_session.id)


def report_judgement(request, game_id, log_id):
    game_session = _get_game_session(game_id)
    if request.method == "POST":
        log = get_object_or_404(QuestionLog, id=log_id, game_session=game_session)
        if log.reported_at is None:
            log.reported_at = timezone.now()
            log.save(update_fields=["reported_at"])
        messages.success(request, "판정 신고가 접수되었어요. 확인 후 진행자 판정에 반영할게요.")
    return redirect("game:play", game_id=game_session.id)


def use_hint(request, game_id):
    game_session = _get_game_session(game_id)
    cleared_response = _redirect_if_cleared(game_session)
    if cleared_response:
        return cleared_response

    if request.method == "POST" and game_session.hint_used_count < MAX_HINT_COUNT:
        next_hint = _pick_next_hint(game_session)
        if next_hint:
            game_session.revealed_hint_texts = _get_revealed_hints(game_session) + [next_hint]
            game_session.hint_used_count += 1
            game_session.save(update_fields=["revealed_hint_texts", "hint_used_count"])

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
            judgement = classify_final_answer(
                scenario=game_session.puzzle.scenario,
                answer_text=game_session.puzzle.answer_text,
                answer_checkpoints=game_session.puzzle.get_answer_checkpoints(),
                submitted_answer=submitted_answer,
            )
        except AIServiceError as exc:
            messages.error(request, str(exc))
            return redirect("game:play", game_id=game_session.id)

        if judgement.label == FINAL_ANSWER_CORRECT:
            game_session.mark_cleared(submitted_answer)
            return redirect("game:result", game_id=game_session.id)

        request.session[f"final_answer_feedback_{game_session.id}"] = {
            "label": judgement.label,
            "met_count": judgement.met_count,
            "total_count": judgement.total_count,
            "submitted_answer": submitted_answer,
        }

    return redirect("game:play", game_id=game_session.id)


def result_view(request, game_id):
    game_session = _get_game_session(game_id)
    if game_session.status != GameSession.STATUS_CLEARED:
        return redirect("game:play", game_id=game_session.id)

    question_count = game_session.question_logs.count()
    game_session.question_count_value = question_count
    return render(
        request,
        "game/result.html",
        {
            "game_session": game_session,
            "puzzle": game_session.puzzle,
            "question_count": question_count,
            "score": game_session.score,
        },
    )
