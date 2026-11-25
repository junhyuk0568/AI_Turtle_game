from django.conf import settings
from django.contrib import messages
from django.core.cache import cache
from django.db.models import Count
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone

from .accounts import remember_guest_key
from .models import GameSession, Puzzle, QuestionLog
from .services import AIServiceError, FINAL_ANSWER_CORRECT, classify_final_answer, classify_question


HINT_FIELDS = ("hint1", "hint2", "hint3")
MAX_HINT_COUNT = len(HINT_FIELDS)
MAX_QUESTION_LENGTH = 500
MAX_ANSWER_LENGTH = 2000
RATE_LIMIT_MESSAGE = "요청이 너무 많아요. 1분 정도 기다렸다가 다시 시도해 주세요."


def _client_owns_game(request, game_session):
    if game_session.user_id:
        return request.user.is_authenticated and request.user.pk == game_session.user_id
    session_key = request.session.session_key
    return bool(session_key) and session_key == game_session.session_key


def _get_game_session(request, game_id):
    game_session = get_object_or_404(GameSession.objects.select_related("puzzle"), id=game_id)
    # Game IDs are sequential, so never serve a game to anyone but its owner.
    if not _client_owns_game(request, game_session):
        raise Http404("게임을 찾을 수 없습니다.")
    return game_session


def _consume_ai_call_quota(request):
    """Fixed one-minute window per client IP for billed Claude calls."""
    limit = settings.AI_CALLS_PER_MINUTE
    if limit <= 0:
        return True
    key = f"game:ai-calls:{request.META.get('REMOTE_ADDR', 'unknown')}"
    if cache.add(key, 1, timeout=60):
        return True
    try:
        return cache.incr(key) <= limit
    except ValueError:
        cache.set(key, 1, timeout=60)
        return True


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




def _visitor_games(request):
    if request.user.is_authenticated:
        return GameSession.objects.filter(user=request.user)
    if request.session.session_key:
        return GameSession.objects.filter(session_key=request.session.session_key, user__isnull=True)
    return GameSession.objects.none()


def home(request):
    if not request.user.is_authenticated:
        remember_guest_key(request)
    puzzles = list(Puzzle.objects.filter(is_active=True))
    games = _visitor_games(request).filter(puzzle__is_active=True).annotate(question_count_value=Count("question_logs"))
    active_games = games.filter(status=GameSession.STATUS_PLAYING).select_related("puzzle")

    best_scores = {}
    for game in games.filter(status=GameSession.STATUS_CLEARED):
        best_scores[game.puzzle_id] = max(best_scores.get(game.puzzle_id, 0), game.score)
    for puzzle in puzzles:
        puzzle.best_score = best_scores.get(puzzle.id)

    return render(request, "game/home.html", {"puzzles": puzzles, "active_games": active_games})


def start_game(request, puzzle_id):
    puzzle = get_object_or_404(Puzzle, id=puzzle_id, is_active=True)

    if not request.session.session_key:
        request.session.create()
    if not request.user.is_authenticated:
        remember_guest_key(request)

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
    game_session = _get_game_session(request, game_id)
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


def _wants_json(request):
    return "application/json" in request.headers.get("Accept", "")


def _judge_and_log_question(request, game_session, question_text):
    """Return (QuestionLog, None, None) on success or (None, message, level) when refused."""
    if not question_text:
        return None, "질문을 입력해 주세요.", messages.WARNING
    if len(question_text) > MAX_QUESTION_LENGTH:
        return None, f"질문은 {MAX_QUESTION_LENGTH}자 이하로 입력해주세요.", messages.ERROR
    if game_session.question_logs.filter(question_text=question_text).exists():
        return None, "이미 같은 질문을 했습니다.", messages.WARNING
    if game_session.question_logs.count() >= settings.MAX_QUESTIONS_PER_GAME:
        return (
            None,
            f"이 게임에서 할 수 있는 질문 {settings.MAX_QUESTIONS_PER_GAME}개를 모두 사용했어요. 정답을 말해 보세요.",
            messages.ERROR,
        )
    if not _consume_ai_call_quota(request):
        return None, RATE_LIMIT_MESSAGE, messages.ERROR

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
        return None, str(exc), messages.ERROR

    log = QuestionLog.objects.create(
        game_session=game_session,
        question_text=question_text,
        answer_label=judgement.label,
        revealed_checkpoints=judgement.revealed_checkpoints,
    )
    return log, None, None


def ask_question(request, game_id):
    game_session = _get_game_session(request, game_id)
    wants_json = _wants_json(request)
    if game_session.status == GameSession.STATUS_CLEARED:
        result_url = reverse("game:result", args=[game_session.id])
        if wants_json:
            return JsonResponse({"ok": False, "message": "이미 끝난 게임입니다.", "redirect": result_url})
        return redirect(result_url)

    if request.method != "POST":
        return redirect("game:play", game_id=game_session.id)

    question_text = request.POST.get("question_text", "").strip()
    log, error, level = _judge_and_log_question(request, game_session, question_text)

    if wants_json:
        if error:
            return JsonResponse({"ok": False, "message": error})
        html = render_to_string(
            "game/_question_exchange.html", {"log": log, "game_session": game_session}, request=request
        )
        return JsonResponse({"ok": True, "html": html, "question_count": game_session.question_logs.count()})

    if error and question_text:
        messages.add_message(request, level, error)
    return redirect("game:play", game_id=game_session.id)


def report_judgement(request, game_id, log_id):
    game_session = _get_game_session(request, game_id)
    if request.method == "POST":
        log = get_object_or_404(QuestionLog, id=log_id, game_session=game_session)
        if log.reported_at is None:
            log.reported_at = timezone.now()
            log.save(update_fields=["reported_at"])
        messages.success(request, "판정 신고가 접수되었어요. 확인 후 진행자 판정에 반영할게요.")
    return redirect("game:play", game_id=game_session.id)


def use_hint(request, game_id):
    game_session = _get_game_session(request, game_id)
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
    game_session = _get_game_session(request, game_id)
    cleared_response = _redirect_if_cleared(game_session)
    if cleared_response:
        return cleared_response

    if request.method == "POST":
        submitted_answer = request.POST.get("submitted_answer", "").strip()
        if len(submitted_answer) > MAX_ANSWER_LENGTH:
            messages.error(request, f"정답은 {MAX_ANSWER_LENGTH}자 이하로 입력해주세요.")
            return redirect("game:play", game_id=game_session.id)

        if submitted_answer and not _consume_ai_call_quota(request):
            messages.error(request, RATE_LIMIT_MESSAGE)
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
    game_session = _get_game_session(request, game_id)
    if game_session.status != GameSession.STATUS_CLEARED:
        return redirect("game:play", game_id=game_session.id)

    question_logs = list(game_session.question_logs.order_by("created_at"))
    game_session.question_count_value = len(question_logs)
    return render(
        request,
        "game/result.html",
        {
            "game_session": game_session,
            "puzzle": game_session.puzzle,
            "question_count": len(question_logs),
            "question_logs": question_logs,
            "score": game_session.score,
        },
    )
