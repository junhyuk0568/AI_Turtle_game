from django.conf import settings
from django.db import models
from django.utils import timezone


class Puzzle(models.Model):
    title = models.CharField(max_length=100)
    scenario = models.TextField()
    answer_text = models.TextField()
    answer_checkpoints = models.TextField(
        blank=True,
        help_text="정답으로 인정하기 위해 포함되어야 하는 핵심 조건을 줄마다 하나씩 입력하세요.",
    )
    question_yes_facts = models.TextField(
        blank=True,
        help_text="'맞습니다'로 답해야 하는 사실을 줄마다 하나씩 입력하세요.",
    )
    question_no_facts = models.TextField(
        blank=True,
        help_text="'아닙니다'로 답해야 하는 사실을 줄마다 하나씩 입력하세요.",
    )
    question_irrelevant_facts = models.TextField(
        blank=True,
        help_text="'관계없습니다'로 답해야 하는 주변 정보를 줄마다 하나씩 입력하세요.",
    )
    question_ambiguous_examples = models.TextField(
        blank=True,
        help_text="'질문이 모호합니다'로 답해야 하는 예시를 줄마다 하나씩 입력하세요.",
    )
    checkpoint_hints = models.TextField(
        blank=True,
        help_text="정답 체크포인트와 같은 순서로, 각 체크포인트 쪽으로 이끄는 힌트를 줄마다 하나씩 입력하세요.",
    )
    hint1 = models.CharField(max_length=255, blank=True)
    hint2 = models.CharField(max_length=255, blank=True)
    hint3 = models.CharField(max_length=255, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return self.title

    def get_answer_checkpoints(self):
        return [line.strip() for line in self.answer_checkpoints.splitlines() if line.strip()]

    def get_checkpoint_hints(self):
        return [line.strip() for line in self.checkpoint_hints.splitlines()]

    def get_question_criteria(self):
        return {
            "yes": _split_lines(self.question_yes_facts),
            "no": _split_lines(self.question_no_facts),
            "irrelevant": _split_lines(self.question_irrelevant_facts),
            "ambiguous": _split_lines(self.question_ambiguous_examples),
        }


def _split_lines(text):
    return [line.strip() for line in text.splitlines() if line.strip()]


class GameSession(models.Model):
    SCORE_START = 1000
    SCORE_PER_QUESTION = 20
    SCORE_PER_HINT = 150

    STATUS_PLAYING = "playing"
    STATUS_CLEARED = "cleared"
    STATUS_CHOICES = [
        (STATUS_PLAYING, "Playing"),
        (STATUS_CLEARED, "Cleared"),
    ]

    puzzle = models.ForeignKey(Puzzle, on_delete=models.CASCADE, related_name="game_sessions")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="game_sessions",
    )
    session_key = models.CharField(max_length=40, blank=True)
    hint_used_count = models.PositiveSmallIntegerField(default=0)
    revealed_hint_texts = models.JSONField(default=list, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PLAYING)
    submitted_answer = models.TextField(blank=True)
    cleared_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.puzzle.title} - {self.status}"

    def mark_cleared(self, submitted_answer):
        self.status = self.STATUS_CLEARED
        self.submitted_answer = submitted_answer
        self.cleared_at = timezone.now()
        self.save(update_fields=["status", "submitted_answer", "cleared_at"])

    def revealed_checkpoint_numbers(self):
        checkpoint_count = len(self.puzzle.get_answer_checkpoints())
        numbers = set()
        for revealed in self.question_logs.values_list("revealed_checkpoints", flat=True):
            for number in revealed or []:
                if isinstance(number, int) and 1 <= number <= checkpoint_count:
                    numbers.add(number)
        return numbers

    @property
    def score(self):
        question_count = getattr(self, "question_count_value", None)
        if question_count is None:
            question_count = self.question_logs.count()
        penalty = question_count * self.SCORE_PER_QUESTION + self.hint_used_count * self.SCORE_PER_HINT
        return max(0, self.SCORE_START - penalty)


class QuestionLog(models.Model):
    ANSWER_LABEL_AMBIGUOUS = "AMBIGUOUS"

    game_session = models.ForeignKey(GameSession, on_delete=models.CASCADE, related_name="question_logs")
    question_text = models.TextField()
    answer_label = models.CharField(max_length=20, default=ANSWER_LABEL_AMBIGUOUS)
    revealed_checkpoints = models.JSONField(default=list, blank=True)
    reported_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Question #{self.id} - {self.answer_label}"


class QuestionTestCase(models.Model):
    LABEL_YES = "맞습니다"
    LABEL_PARTIAL = "일부만 맞습니다"
    LABEL_NO = "아닙니다"
    LABEL_AMBIGUOUS = "질문이 모호합니다"
    LABEL_IRRELEVANT = "관계없습니다"
    LABEL_CHOICES = [
        (LABEL_YES, LABEL_YES),
        (LABEL_PARTIAL, LABEL_PARTIAL),
        (LABEL_NO, LABEL_NO),
        (LABEL_AMBIGUOUS, LABEL_AMBIGUOUS),
        (LABEL_IRRELEVANT, LABEL_IRRELEVANT),
    ]

    puzzle = models.ForeignKey(Puzzle, on_delete=models.CASCADE, related_name="question_test_cases")
    question_text = models.TextField()
    expected_label = models.CharField(max_length=20, choices=LABEL_CHOICES)
    last_answer_label = models.CharField(max_length=20, blank=True)
    last_passed = models.BooleanField(null=True, blank=True)
    last_run_at = models.DateTimeField(null=True, blank=True)
    memo = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["puzzle", "id"]

    def __str__(self):
        return f"{self.puzzle.title} - {self.expected_label}"

    def mark_result(self, answer_label):
        self.last_answer_label = answer_label
        self.last_passed = answer_label == self.expected_label
        self.last_run_at = timezone.now()
        self.save(update_fields=["last_answer_label", "last_passed", "last_run_at"])


class AIUsageLog(models.Model):
    operation = models.CharField(max_length=40)
    model = models.CharField(max_length=100)
    input_tokens = models.PositiveIntegerField(default=0)
    cache_creation_input_tokens = models.PositiveIntegerField(default=0)
    cache_read_input_tokens = models.PositiveIntegerField(default=0)
    output_tokens = models.PositiveIntegerField(default=0)
    total_tokens = models.PositiveIntegerField(default=0)
    success = models.BooleanField(default=True)
    error_message = models.CharField(max_length=255, blank=True)
    # Indexed: the daily budget check sums today's rows on every billed call.
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.operation} - {self.total_tokens} tokens"


class DailyUsage(models.Model):
    """Billed Claude calls per player per day (identity is "user:<id>" or "guest:<session key>")."""

    day = models.DateField()
    identity = models.CharField(max_length=80)
    count = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["-day", "-count"]
        constraints = [models.UniqueConstraint(fields=["day", "identity"], name="unique_daily_usage")]

    def __str__(self):
        return f"{self.day} {self.identity}: {self.count}"


NICKNAME_PATTERN = r"^[0-9A-Za-z가-힣_]{2,12}$"
RESERVED_NICKNAMES = {"admin", "administrator", "root", "관리자", "운영자", "진행자", "게스트"}


class PlayerProfile(models.Model):
    """Public identity on rankings. Google name and email are never shown."""

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="player_profile")
    nickname = models.CharField(max_length=12, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.nickname
