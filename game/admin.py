from django.contrib import admin
from django.shortcuts import redirect
from django.urls import path, reverse

from .models import GameSession, Puzzle, QuestionLog, QuestionTestCase
from .services import classify_question, generate_puzzle_criteria


class QuestionTestCaseInline(admin.TabularInline):
    model = QuestionTestCase
    extra = 1
    fields = (
        "question_text",
        "expected_label",
        "memo",
        "last_answer_label",
        "last_passed",
        "last_run_at",
    )
    readonly_fields = ("last_answer_label", "last_passed", "last_run_at")


@admin.register(Puzzle)
class PuzzleAdmin(admin.ModelAdmin):
    change_form_template = "admin/game/puzzle/change_form.html"
    list_display = ("title", "is_active", "created_at", "updated_at")
    search_fields = (
        "title",
        "scenario",
        "answer_text",
        "answer_checkpoints",
        "question_yes_facts",
        "question_no_facts",
        "question_irrelevant_facts",
        "question_ambiguous_examples",
    )
    list_filter = ("is_active", "created_at", "updated_at")
    actions = ("generate_ai_criteria", "run_question_tests")
    inlines = (QuestionTestCaseInline,)
    fieldsets = (
        (None, {"fields": ("title", "scenario", "answer_text", "is_active")}),
        (
            "AI 판정 기준",
            {
                "fields": (
                    "answer_checkpoints",
                    "question_yes_facts",
                    "question_no_facts",
                    "question_irrelevant_facts",
                    "question_ambiguous_examples",
                )
            },
        ),
        ("힌트", {"fields": ("hint1", "hint2", "hint3")}),
    )

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "<int:object_id>/generate-ai-criteria/",
                self.admin_site.admin_view(self.generate_ai_criteria_view),
                name="game_puzzle_generate_ai_criteria",
            ),
            path(
                "<int:object_id>/run-question-tests/",
                self.admin_site.admin_view(self.run_question_tests_view),
                name="game_puzzle_run_question_tests",
            ),
        ]
        return custom_urls + urls

    def _apply_generated_criteria(self, puzzle):
        criteria = generate_puzzle_criteria(puzzle.scenario, puzzle.answer_text)
        puzzle.answer_checkpoints = "\n".join(criteria.get("answer_checkpoints", []))
        puzzle.question_yes_facts = "\n".join(criteria.get("question_yes_facts", []))
        puzzle.question_no_facts = "\n".join(criteria.get("question_no_facts", []))
        puzzle.question_irrelevant_facts = "\n".join(criteria.get("question_irrelevant_facts", []))
        puzzle.question_ambiguous_examples = "\n".join(criteria.get("question_ambiguous_examples", []))
        puzzle.save(
            update_fields=[
                "answer_checkpoints",
                "question_yes_facts",
                "question_no_facts",
                "question_irrelevant_facts",
                "question_ambiguous_examples",
                "updated_at",
            ]
        )

    def generate_ai_criteria_view(self, request, object_id):
        puzzle = self.get_object(request, object_id)
        if puzzle is None:
            self.message_user(request, "문제를 찾을 수 없습니다.", level="error")
            return redirect("..")

        self._apply_generated_criteria(puzzle)
        self.message_user(request, "AI 판정 기준을 생성했습니다.")
        return redirect(reverse("admin:game_puzzle_change", args=[object_id]))

    def _run_question_tests_for_puzzle(self, puzzle):
        total_count = 0
        passed_count = 0
        for test_case in puzzle.question_test_cases.all():
            answer_label = classify_question(
                scenario=puzzle.scenario,
                answer_text=puzzle.answer_text,
                question_text=test_case.question_text,
                question_criteria=puzzle.get_question_criteria(),
            )
            test_case.mark_result(answer_label)
            total_count += 1
            if test_case.last_passed:
                passed_count += 1
        return passed_count, total_count

    def run_question_tests_view(self, request, object_id):
        puzzle = self.get_object(request, object_id)
        if puzzle is None:
            self.message_user(request, "문제를 찾을 수 없습니다.", level="error")
            return redirect("..")

        passed_count, total_count = self._run_question_tests_for_puzzle(puzzle)
        self.message_user(request, f"테스트 질문 {passed_count}/{total_count}개가 통과했습니다.")
        return redirect(reverse("admin:game_puzzle_change", args=[object_id]))

    @admin.action(description="선택한 문제의 AI 판정 기준 생성")
    def generate_ai_criteria(self, request, queryset):
        updated_count = 0
        for puzzle in queryset:
            self._apply_generated_criteria(puzzle)
            updated_count += 1

        self.message_user(request, f"{updated_count}개 문제의 판정 기준을 생성했습니다.")

    @admin.action(description="선택한 문제의 테스트 질문 실행")
    def run_question_tests(self, request, queryset):
        total_count = 0
        passed_count = 0
        for puzzle in queryset:
            puzzle_passed_count, puzzle_total_count = self._run_question_tests_for_puzzle(puzzle)
            passed_count += puzzle_passed_count
            total_count += puzzle_total_count

        self.message_user(request, f"테스트 질문 {passed_count}/{total_count}개가 통과했습니다.")


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


@admin.register(QuestionTestCase)
class QuestionTestCaseAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "puzzle",
        "short_question",
        "expected_label",
        "last_answer_label",
        "last_passed",
        "last_run_at",
    )
    search_fields = ("question_text", "expected_label", "last_answer_label", "puzzle__title", "memo")
    list_filter = ("expected_label", "last_passed", "last_run_at", "created_at")
    readonly_fields = ("last_answer_label", "last_passed", "last_run_at", "created_at")
    actions = ("run_selected_tests",)

    @admin.display(description="질문")
    def short_question(self, obj):
        return obj.question_text[:40]

    @admin.action(description="선택한 테스트 질문 실행")
    def run_selected_tests(self, request, queryset):
        total_count = 0
        passed_count = 0
        for test_case in queryset.select_related("puzzle"):
            answer_label = classify_question(
                scenario=test_case.puzzle.scenario,
                answer_text=test_case.puzzle.answer_text,
                question_text=test_case.question_text,
                question_criteria=test_case.puzzle.get_question_criteria(),
            )
            test_case.mark_result(answer_label)
            total_count += 1
            if test_case.last_passed:
                passed_count += 1

        self.message_user(request, f"테스트 질문 {passed_count}/{total_count}개가 통과했습니다.")
