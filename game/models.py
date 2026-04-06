from django.conf import settings
from django.db import models


class Puzzle(models.Model):
    title = models.CharField(max_length=100)
    scenario = models.TextField()
    answer_text = models.TextField()
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


class GameSession(models.Model):
    STATUS_PLAYING = "playing"
    STATUS_CHOICES = [
        (STATUS_PLAYING, "Playing"),
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
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.puzzle.title} - {self.status}"


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
