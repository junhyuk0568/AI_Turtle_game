from django.contrib import admin, messages
from django.db.models import Count, Q
from django.shortcuts import redirect
from django.urls import path, reverse

from .models import AIUsageLog, GameSession, Puzzle, QuestionLog, QuestionTestCase
from .services import AIServiceError, classify_question, generate_puzzle_criteria


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
    list_display = ("title", "criteria_ready", "question_test_results", "is_active", "created_at", "updated_at")
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
        ("힌트", {"fields": ("checkpoint_hints", "hint1", "hint2", "hint3")}),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(
            test_count=Count("question_test_cases"),
            passed_test_count=Count("question_test_cases", filter=Q(question_test_cases__last_passed=True)),
        )

    @admin.display(description="판정 기준", boolean=True)
    def criteria_ready(self, obj):
        return all(
            (
                obj.answer_checkpoints.strip(),
                obj.question_yes_facts.strip(),
                obj.question_no_facts.strip(),
                obj.question_irrelevant_facts.strip(),
                obj.question_ambiguous_examples.strip(),
            )
        )

    @admin.display(description="질문 테스트")
    def question_test_results(self, obj):
        return f"{obj.passed_test_count}/{obj.test_count}"

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
        puzzle.checkpoint_hints = "\n".join(criteria.get("checkpoint_hints", []))
        puzzle.question_yes_facts = "\n".join(criteria.get("question_yes_facts", []))
        puzzle.question_no_facts = "\n".join(criteria.get("question_no_facts", []))
        puzzle.question_irrelevant_facts = "\n".join(criteria.get("question_irrelevant_facts", []))
        puzzle.question_ambiguous_examples = "\n".join(criteria.get("question_ambiguous_examples", []))
        puzzle.save(
            update_fields=[
                "answer_checkpoints",
                "checkpoint_hints",
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

        try:
            self._apply_generated_criteria(puzzle)
        except AIServiceError as exc:
            self.message_user(request, str(exc), level=messages.ERROR)
            return redirect(reverse("admin:game_puzzle_change", args=[object_id]))

        self.message_user(request, "AI 판정 기준을 생성했습니다.")
        return redirect(reverse("admin:game_puzzle_change", args=[object_id]))

    def _run_question_tests_for_puzzle(self, puzzle):
        total_count = 0
        passed_count = 0
        for test_case in puzzle.question_test_cases.all():
            judgement = classify_question(
                scenario=puzzle.scenario,
                answer_text=puzzle.answer_text,
                question_text=test_case.question_text,
                question_criteria=puzzle.get_question_criteria(),
                answer_checkpoints=puzzle.get_answer_checkpoints(),
            )
            test_case.mark_result(judgement.label)
            total_count += 1
            if test_case.last_passed:
                passed_count += 1
        return passed_count, total_count

    def run_question_tests_view(self, request, object_id):
        puzzle = self.get_object(request, object_id)
        if puzzle is None:
            self.message_user(request, "문제를 찾을 수 없습니다.", level="error")
            return redirect("..")

        try:
            passed_count, total_count = self._run_question_tests_for_puzzle(puzzle)
        except AIServiceError as exc:
            self.message_user(request, str(exc), level=messages.ERROR)
            return redirect(reverse("admin:game_puzzle_change", args=[object_id]))

        self.message_user(request, f"테스트 질문 {passed_count}/{total_count}개가 통과했습니다.")
        return redirect(reverse("admin:game_puzzle_change", args=[object_id]))

    @admin.action(description="선택한 문제의 AI 판정 기준 생성")
    def generate_ai_criteria(self, request, queryset):
        updated_count = 0
        for puzzle in queryset:
            try:
                self._apply_generated_criteria(puzzle)
                updated_count += 1
            except AIServiceError as exc:
                self.message_user(request, f"{puzzle}: {exc}", level=messages.ERROR)

        self.message_user(request, f"{updated_count}개 문제의 판정 기준을 생성했습니다.")

    @admin.action(description="선택한 문제의 테스트 질문 실행")
    def run_question_tests(self, request, queryset):
        total_count = 0
        passed_count = 0
        for puzzle in queryset:
            try:
                puzzle_passed_count, puzzle_total_count = self._run_question_tests_for_puzzle(puzzle)
            except AIServiceError as exc:
                self.message_user(request, f"{puzzle}: {exc}", level=messages.ERROR)
                continue
            passed_count += puzzle_passed_count
            total_count += puzzle_total_count

        self.message_user(request, f"테스트 질문 {passed_count}/{total_count}개가 통과했습니다.")


@admin.register(GameSession)
class GameSessionAdmin(admin.ModelAdmin):
    list_display = ("id", "puzzle", "user", "question_count", "hint_used_count", "score", "status", "created_at")
    search_fields = ("puzzle__title", "user__username", "session_key")
    list_filter = ("status", "created_at", "hint_used_count")

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(question_count_value=Count("question_logs"))

    @admin.display(description="질문 수")
    def question_count(self, obj):
        return obj.question_count_value

    @admin.display(description="점수")
    def score(self, obj):
        return obj.score


def _make_report_to_test_action(index, expected_label):
    def action(modeladmin, request, queryset):
        created_count = 0
        for log in queryset.select_related("game_session__puzzle"):
            _, created = QuestionTestCase.objects.get_or_create(
                puzzle=log.game_session.puzzle,
                question_text=log.question_text,
                defaults={
                    "expected_label": expected_label,
                    "memo": f"플레이어 판정 신고에서 등록 (기존 판정: {log.answer_label})"[:255],
                },
            )
            if created:
                created_count += 1
        modeladmin.message_user(
            request,
            f"테스트 질문 {created_count}개를 기대 판정 '{expected_label}'으로 등록했습니다. 이미 있던 질문은 건너뛰었습니다.",
        )

    action.__name__ = f"register_as_test_case_{index}"
    action.short_description = f"테스트 질문으로 등록 (기대 판정: {expected_label})"
    return action


@admin.register(QuestionLog)
class QuestionLogAdmin(admin.ModelAdmin):
    list_display = ("id", "game_session", "short_question", "answer_label", "reported_at", "created_at")
    search_fields = ("question_text", "answer_label", "game_session__puzzle__title")
    list_filter = ("answer_label", ("reported_at", admin.EmptyFieldListFilter), "created_at")
    actions = [
        _make_report_to_test_action(index, label)
        for index, (label, _) in enumerate(QuestionTestCase.LABEL_CHOICES)
    ]

    @admin.display(description="질문")
    def short_question(self, obj):
        return obj.question_text[:40]


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
            try:
                judgement = classify_question(
                    scenario=test_case.puzzle.scenario,
                    answer_text=test_case.puzzle.answer_text,
                    question_text=test_case.question_text,
                    question_criteria=test_case.puzzle.get_question_criteria(),
                    answer_checkpoints=test_case.puzzle.get_answer_checkpoints(),
                )
            except AIServiceError as exc:
                self.message_user(request, f"{test_case}: {exc}", level=messages.ERROR)
                continue
            test_case.mark_result(judgement.label)
            total_count += 1
            if test_case.last_passed:
                passed_count += 1

        self.message_user(request, f"테스트 질문 {passed_count}/{total_count}개가 통과했습니다.")


@admin.register(AIUsageLog)
class AIUsageLogAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "operation",
        "model",
        "input_tokens",
        "output_tokens",
        "total_tokens",
        "success",
        "created_at",
    )
    list_filter = ("operation", "model", "success", "created_at")
    search_fields = ("operation", "model", "error_message")
    readonly_fields = (
        "operation",
        "model",
        "input_tokens",
        "output_tokens",
        "total_tokens",
        "success",
        "error_message",
        "created_at",
    )

    def has_add_permission(self, request):
        return False
