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


class QuestionLog(models.Model):
    ANSWER_LABEL_AMBIGUOUS = "AMBIGUOUS"

    game_session = models.ForeignKey(GameSession, on_delete=models.CASCADE, related_name="question_logs")
    question_text = models.TextField()
    answer_label = models.CharField(max_length=20, default=ANSWER_LABEL_AMBIGUOUS)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Question #{self.id} - {self.answer_label}"


class QuestionTestCase(models.Model):
    LABEL_YES = "맞습니다"
    LABEL_NO = "아닙니다"
    LABEL_AMBIGUOUS = "질문이 모호합니다"
    LABEL_IRRELEVANT = "관계없습니다"
    LABEL_CHOICES = [
        (LABEL_YES, LABEL_YES),
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
