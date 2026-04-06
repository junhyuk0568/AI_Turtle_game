from django.contrib import admin

from .models import GameSession, Puzzle, QuestionLog


@admin.register(Puzzle)
class PuzzleAdmin(admin.ModelAdmin):
    list_display = ("title", "is_active", "created_at", "updated_at")
    search_fields = ("title", "scenario", "answer_text")
    list_filter = ("is_active", "created_at", "updated_at")


@admin.register(GameSession)
class GameSessionAdmin(admin.ModelAdmin):
    list_display = ("id", "puzzle", "user", "session_key", "hint_used_count", "status", "created_at")
    search_fields = ("puzzle__title", "user__username", "session_key")
    list_filter = ("status", "created_at", "hint_used_count")


@admin.register(QuestionLog)
class QuestionLogAdmin(admin.ModelAdmin):
    list_display = ("id", "game_session", "answer_label", "created_at")
    search_fields = ("question_text", "answer_label", "game_session__puzzle__title")
    list_filter = ("answer_label", "created_at")
