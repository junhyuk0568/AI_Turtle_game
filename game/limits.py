"""Limits on billed Claude calls made by players.

Three checks run before every billed call (question or final answer):
1. Service-wide daily budget, estimated from AIUsageLog token counts.
2. Per-IP one-minute window (shared database cache, so it holds across workers).
3. Per-player daily cap: by account when logged in, else by guest session.
"""

from datetime import datetime, time

from django.conf import settings
from django.core.cache import cache
from django.db.models import F, Sum
from django.utils import timezone

from .models import AIUsageLog, DailyUsage


RATE_LIMIT_MESSAGE = "요청이 너무 많아요. 1분 정도 기다렸다가 다시 시도해 주세요."
BUDGET_MESSAGE = "오늘 준비한 진행자 이용량이 모두 소진됐어요. 내일 다시 찾아와 주세요."


def _start_of_today():
    today = timezone.localdate()
    return timezone.make_aware(datetime.combine(today, time.min))


def estimated_cost_usd(since=None):
    """Estimated spend of all Claude calls since `since` (default: start of today, local time)."""
    totals = AIUsageLog.objects.filter(created_at__gte=since or _start_of_today()).aggregate(
        input=Sum("input_tokens"),
        cache_write=Sum("cache_creation_input_tokens"),
        cache_read=Sum("cache_read_input_tokens"),
        output=Sum("output_tokens"),
    )
    cost_per_million = (
        (totals["input"] or 0) * settings.AI_PRICE_INPUT_PER_MTOK
        + (totals["cache_write"] or 0) * settings.AI_PRICE_CACHE_WRITE_PER_MTOK
        + (totals["cache_read"] or 0) * settings.AI_PRICE_CACHE_READ_PER_MTOK
        + (totals["output"] or 0) * settings.AI_PRICE_OUTPUT_PER_MTOK
    )
    return cost_per_million / 1_000_000


def budget_exhausted():
    budget = settings.DAILY_AI_BUDGET_USD
    return budget > 0 and estimated_cost_usd() >= budget


def _consume_minute_window(request):
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


def _player_identity(request):
    """Return (identity, daily limit) for the visitor making the call."""
    if request.user.is_authenticated:
        return f"user:{request.user.pk}", settings.DAILY_AI_CALLS_PER_ACCOUNT
    if not request.session.session_key:
        request.session.save()
    return f"guest:{request.session.session_key}", settings.DAILY_AI_CALLS_PER_GUEST


def _consume_daily_call(request):
    identity, limit = _player_identity(request)
    if limit <= 0:
        return True
    row, _ = DailyUsage.objects.get_or_create(day=timezone.localdate(), identity=identity)
    # Conditional UPDATE keeps the cap exact when two requests race.
    return DailyUsage.objects.filter(pk=row.pk, count__lt=limit).update(count=F("count") + 1) == 1


def _daily_limit_message(request):
    _, limit = _player_identity(request)
    message = f"오늘 쓸 수 있는 질문·정답 제출 {limit}회를 모두 썼어요. 내일 다시 도전해 주세요."
    if not request.user.is_authenticated and settings.GOOGLE_LOGIN_ENABLED:
        message += f" 로그인하면 하루 {settings.DAILY_AI_CALLS_PER_ACCOUNT}회까지 쓸 수 있어요."
    return message


def consume_billed_call(request):
    """Return None when the call may proceed, else the message to show the player."""
    if budget_exhausted():
        return BUDGET_MESSAGE
    if not _consume_minute_window(request):
        return RATE_LIMIT_MESSAGE
    if not _consume_daily_call(request):
        return _daily_limit_message(request)
    return None
