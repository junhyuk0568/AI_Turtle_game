from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
import json

from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import RequestFactory, TestCase, override_settings, tag
from django.urls import reverse
from django.utils import timezone

from .admin import QuestionLogAdmin
from .limits import estimated_cost_usd
from .rankings import overall_ranking, puzzle_ranking
from .models import AIUsageLog, DailyUsage, GameSession, PlayerProfile, Puzzle, QuestionLog, QuestionTestCase
from .services import (
    FALLBACK_BETA,
    FINAL_ANSWER_CORRECT,
    FINAL_ANSWER_INSUFFICIENT,
    LABEL_NO,
    LABEL_PARTIAL,
    LABEL_YES,
    REFUSAL_MESSAGE,
    AIRefusalError,
    AIServiceError,
    FinalAnswerJudgement,
    QuestionJudgement,
    _classify_final_answer_locally,
    _classify_question_locally,
    _classify_question_with_criteria,
    _generate_puzzle_criteria_locally,
    _normalize_generated_criteria,
    _normalize_label,
    _record_ai_usage,
    classify_final_answer,
    classify_question,
    generate_puzzle_criteria,
)


CHECKPOINTS = [
    "남자는 과거 조난 상황에서 수프를 먹었다.",
    "그때 먹은 수프는 바다거북스프가 아니라 인육 수프였다.",
    "식당에서 진짜 바다거북스프를 먹고 과거의 진실을 깨달았다.",
]


def _fake_response(payload=None, stop_reason="end_turn", category=None):
    text = json.dumps(payload, ensure_ascii=False) if payload is not None else ""
    return SimpleNamespace(
        content=[SimpleNamespace(type="text", text=text)],
        stop_reason=stop_reason,
        stop_details=SimpleNamespace(category=category) if category else None,
        usage=SimpleNamespace(input_tokens=120, output_tokens=30),
        model="claude-opus-5-5",
    )


def _fake_client(response):
    client = MagicMock()
    client.beta.messages.create.return_value = response
    return client


GOOGLE_TEST_SETTINGS = {
    "GOOGLE_LOGIN_ENABLED": True,
    "SOCIALACCOUNT_PROVIDERS": {
        "google": {
            "APPS": [{"client_id": "test-client", "secret": "test-secret", "key": ""}],
            "SCOPE": ["profile", "email"],
        }
    },
}


def _owned_game(client, **fields):
    """Create a game that belongs to the test client's anonymous session."""
    session = client.session
    session.save()
    return GameSession.objects.create(session_key=session.session_key, **fields)


class QuestionClassifierTests(TestCase):
    def test_normalize_label_strips_extra_text(self):
        self.assertEqual(_normalize_label("맞습니다."), "맞습니다")
        self.assertEqual(_normalize_label("결과: 관계없습니다"), "관계없습니다")
        self.assertEqual(_normalize_label("일부만 맞습니다."), LABEL_PARTIAL)
        self.assertEqual(_normalize_label("unknown"), "질문이 모호합니다")

    def test_local_classifier_returns_distinct_labels_for_dev_testing(self):
        cases = {
            "남자는 식당에서 바다거북스프를 먹었나요?": "맞습니다",
            "남자는 다른 사람에게 살해당했나요?": "아닙니다",
            "남자는 원래 자살 계획이 있었나요?": "아닙니다",
            "남자는 바다거북스프를 먹기 전부터 자살할 계획이 있었나요?": "아닙니다",
            "남자는 이상한 기분이 들었나요?": "질문이 모호합니다",
            "남자의 신발 색깔이 중요합니까?": "관계없습니다",
        }

        for question, expected_label in cases.items():
            with self.subTest(question=question):
                self.assertEqual(_classify_question_locally(question), expected_label)

    def test_local_final_answer_classifier(self):
        self.assertEqual(
            _classify_final_answer_locally("남자는 과거 조난 때 먹은 음식이 인육이었다는 걸 수프 맛으로 깨달았다."),
            FINAL_ANSWER_CORRECT,
        )
        self.assertEqual(
            _classify_final_answer_locally("남자는 수프를 먹고 충격을 받았다."),
            FINAL_ANSWER_INSUFFICIENT,
        )

    def test_local_final_answer_uses_checkpoints_when_available(self):
        self.assertEqual(
            _classify_final_answer_locally(
                "남자는 예전에 조난당했을 때 먹은 수프가 인육이었고, 식당에서 진짜 바다거북스프를 먹고 그 사실을 깨달았다.",
                CHECKPOINTS,
            ),
            FINAL_ANSWER_CORRECT,
        )
        self.assertEqual(
            _classify_final_answer_locally("남자는 예전에 조난당했고 식당에서 수프를 먹었다.", CHECKPOINTS),
            FINAL_ANSWER_INSUFFICIENT,
        )

    def test_question_criteria_override_keyword_fallback(self):
        criteria = {
            "yes": ["남자는 집에 돌아온 뒤 자살했다."],
            "no": ["남자는 원래 자살 계획이 있었다."],
            "irrelevant": ["남자의 신발 색깔"],
            "ambiguous": ["남자는 이상한 기분이 들었나요?"],
        }

        self.assertEqual(_classify_question_with_criteria("남자는 원래 자살 계획이 있었나요?", criteria), "아닙니다")
        self.assertEqual(_classify_question_with_criteria("남자는 집에 돌아온 뒤 자살했나요?", criteria), "맞습니다")

    def test_generate_puzzle_criteria_local_fallback(self):
        criteria = _generate_puzzle_criteria_locally(
            "한 남자가 식당에서 바다거북스프를 먹고 집에 돌아온 뒤 자살했다.",
            "그는 과거 조난 상황에서 먹었던 수프가 인육 수프였다는 사실을 깨달았다.",
        )

        self.assertIn("남자는 원래 자살 계획이 있었다.", criteria["question_no_facts"])
        self.assertEqual(len(criteria["checkpoint_hints"]), len(criteria["answer_checkpoints"]))

    def test_generated_checkpoint_hints_are_aligned_to_checkpoints(self):
        criteria = _normalize_generated_criteria(
            {"answer_checkpoints": ["a", "b", "c"], "checkpoint_hints": ["h1", "h2", "h3", "extra"]}
        )
        self.assertEqual(criteria["checkpoint_hints"], ["h1", "h2", "h3"])

        criteria = _normalize_generated_criteria({"answer_checkpoints": ["a", "b"], "checkpoint_hints": ["h1"]})
        self.assertEqual(criteria["checkpoint_hints"], ["h1", ""])

    def test_question_test_case_stores_last_result(self):
        puzzle = Puzzle.objects.create(
            title="테스트 문제",
            scenario="한 남자가 식당에서 수프를 먹고 집에 돌아온 뒤 자살했다.",
            answer_text="그는 식당의 수프를 통해 과거의 진실을 깨달았다.",
            question_yes_facts="남자는 식당에서 수프를 먹었다.",
        )
        test_case = QuestionTestCase.objects.create(
            puzzle=puzzle,
            question_text="남자는 식당에서 수프를 먹었나요?",
            expected_label="맞습니다",
        )

        answer_label = _classify_question_with_criteria(test_case.question_text, puzzle.get_question_criteria())
        test_case.mark_result(answer_label)

        self.assertEqual(test_case.last_answer_label, "맞습니다")
        self.assertTrue(test_case.last_passed)
        self.assertIsNotNone(test_case.last_run_at)


@override_settings(
    ANTHROPIC_API_KEY="test-key", CLAUDE_MODEL="claude-sonnet-5-5", CLAUDE_EFFORT="low", CLAUDE_REFUSAL_FALLBACK=True
)
class ClaudeServiceTests(TestCase):
    def _classify(self, payload, **kwargs):
        client = _fake_client(_fake_response(payload))
        with patch("game.services._get_client", return_value=client):
            judgement = classify_question(
                scenario="시나리오",
                answer_text="진실",
                question_text="새 질문",
                answer_checkpoints=CHECKPOINTS,
                **kwargs,
            )
        return judgement, client.beta.messages.create.call_args.kwargs

    def test_question_request_uses_structured_output_history_and_fallback(self):
        judgement, request = self._classify(
            {"label": LABEL_YES, "revealed_checkpoints": [1]},
            history=[("이전 질문", LABEL_NO)],
        )

        self.assertEqual(judgement, QuestionJudgement(label=LABEL_YES, revealed_checkpoints=[1]))
        self.assertEqual(request["model"], "claude-sonnet-5-5")
        self.assertEqual(request["output_config"]["format"]["type"], "json_schema")
        self.assertIn(LABEL_PARTIAL, request["output_config"]["format"]["schema"]["properties"]["label"]["enum"])
        self.assertEqual(request["output_config"]["effort"], "low")
        self.assertEqual(request["fallbacks"], "default")
        self.assertEqual(request["betas"], [FALLBACK_BETA])
        self.assertIn("이전 질문", request["messages"][0]["content"])
        self.assertIn("새 질문", request["messages"][0]["content"])
        self.assertIn("진실", request["system"][0]["text"])
        self.assertNotIn("새 질문", request["system"][0]["text"])

    @override_settings(CLAUDE_REFUSAL_FALLBACK=False)
    def test_fallback_can_be_disabled_for_models_without_it(self):
        _, request = self._classify({"label": LABEL_NO, "revealed_checkpoints": []})

        self.assertNotIn("fallbacks", request)
        self.assertNotIn("betas", request)

    def test_question_judgement_drops_invalid_checkpoints_and_non_confirming_extras(self):
        judgement, _ = self._classify({"label": LABEL_PARTIAL, "revealed_checkpoints": [2, 9, 2, 0]})
        self.assertEqual(judgement.revealed_checkpoints, [2])

        judgement, _ = self._classify({"label": LABEL_NO, "revealed_checkpoints": [1]})
        self.assertEqual(judgement, QuestionJudgement(label=LABEL_NO))

    def test_unknown_label_raises_service_error(self):
        with self.assertRaises(AIServiceError):
            self._classify({"label": "몰라요", "revealed_checkpoints": []})

    def test_refusal_raises_friendly_error_and_logs_category(self):
        client = _fake_client(_fake_response(stop_reason="refusal", category="general_harms"))
        with patch("game.services._get_client", return_value=client):
            with self.assertRaisesMessage(AIRefusalError, REFUSAL_MESSAGE):
                classify_question(scenario="s", answer_text="a", question_text="q")

        log = AIUsageLog.objects.get()
        self.assertFalse(log.success)
        self.assertEqual(log.error_message, "refusal: general_harms")

    def test_api_failure_is_wrapped(self):
        client = MagicMock()
        client.beta.messages.create.side_effect = RuntimeError("network down")
        with patch("game.services._get_client", return_value=client):
            with self.assertRaises(AIServiceError):
                classify_question(scenario="s", answer_text="a", question_text="q")

    @override_settings(ANTHROPIC_API_KEY="")
    def test_missing_api_key_raises_service_error(self):
        with self.assertRaises(AIServiceError):
            classify_question(scenario="s", answer_text="a", question_text="q")

    def test_final_answer_requires_every_checkpoint(self):
        payload = {
            "checkpoints": [{"number": 1, "met": True}, {"number": 2, "met": True}, {"number": 3, "met": False}],
            "explains_core_truth": True,
        }
        client = _fake_client(_fake_response(payload))
        with patch("game.services._get_client", return_value=client):
            judgement = classify_final_answer("s", "a", "답변", CHECKPOINTS)

        self.assertEqual(judgement, FinalAnswerJudgement(label=FINAL_ANSWER_INSUFFICIENT, met_count=2, total_count=3))

        payload["checkpoints"][2]["met"] = True
        client = _fake_client(_fake_response(payload))
        with patch("game.services._get_client", return_value=client):
            judgement = classify_final_answer("s", "a", "답변", CHECKPOINTS)

        self.assertEqual(judgement.label, FINAL_ANSWER_CORRECT)

    def test_final_answer_without_checkpoints_uses_core_truth_flag(self):
        client = _fake_client(_fake_response({"checkpoints": [], "explains_core_truth": True}))
        with patch("game.services._get_client", return_value=client):
            judgement = classify_final_answer("s", "a", "답변", [])

        self.assertEqual(judgement.label, FINAL_ANSWER_CORRECT)

    def test_empty_final_answer_skips_api(self):
        with patch("game.services._get_client") as get_client:
            judgement = classify_final_answer("s", "a", "   ", CHECKPOINTS)

        get_client.assert_not_called()
        self.assertEqual(judgement.label, FINAL_ANSWER_INSUFFICIENT)

    def test_generate_criteria_returns_aligned_hints(self):
        payload = {
            "answer_checkpoints": ["c1", "c2"],
            "checkpoint_hints": ["h1"],
            "question_yes_facts": ["y"],
            "question_no_facts": ["n"],
            "question_irrelevant_facts": ["i"],
            "question_ambiguous_examples": ["m"],
        }
        client = _fake_client(_fake_response(payload))
        with patch("game.services._get_client", return_value=client):
            criteria = generate_puzzle_criteria("s", "a")

        self.assertEqual(criteria["checkpoint_hints"], ["h1", ""])


@override_settings(AI_CALLS_PER_MINUTE=0)
class GameFlowTests(TestCase):
    def setUp(self):
        self.puzzle = Puzzle.objects.create(
            title="테스트 문제",
            scenario="남자가 식당에서 수프를 먹고 집에 돌아갔다.",
            answer_text="남자는 수프를 먹고 과거의 진실을 깨달았다.",
            answer_checkpoints="\n".join(CHECKPOINTS),
        )
        self.game_session = _owned_game(self.client, puzzle=self.puzzle, status=GameSession.STATUS_PLAYING)

    def _ask(self, question, judgement):
        with patch("game.views.classify_question", return_value=judgement) as classifier:
            response = self.client.post(
                reverse("game:ask_question", args=[self.game_session.id]),
                {"question_text": question},
                follow=True,
            )
        return response, classifier

    def test_result_page_redirects_until_session_is_cleared(self):
        response = self.client.get(reverse("game:result", args=[self.game_session.id]))

        self.assertRedirects(response, reverse("game:play", args=[self.game_session.id]))

    def test_result_page_is_available_after_session_is_cleared(self):
        game_session = _owned_game(self.client, puzzle=self.puzzle, status=GameSession.STATUS_CLEARED)

        response = self.client.get(reverse("game:result", args=[game_session.id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.puzzle.answer_text)
        self.assertContains(response, "1000")

    def test_question_stores_judgement_without_progress_display(self):
        response, _ = self._ask(
            "남자는 예전에 조난당한 적이 있나요?",
            QuestionJudgement(label=LABEL_YES, revealed_checkpoints=[1]),
        )

        log = self.game_session.question_logs.get()
        self.assertEqual(log.revealed_checkpoints, [1])
        self.assertContains(response, "그렇습니다.")
        self.assertNotContains(response, "진실 탐색도")
        self.assertNotContains(response, "밝혀냈어요")
        self.assertNotContains(response, "핵심 질문")

    def test_answer_dialog_states_required_keyword_count(self):
        response = self.client.get(reverse("game:play", args=[self.game_session.id]))

        self.assertContains(response, "정답에는 핵심 키워드 3개가 모두 포함되어야 합니다.")

    def test_required_keyword_count_is_hidden_without_checkpoints(self):
        puzzle = Puzzle.objects.create(title="체크포인트 없음", scenario="s", answer_text="a")
        game_session = _owned_game(self.client, puzzle=puzzle)

        response = self.client.get(reverse("game:play", args=[game_session.id]))

        self.assertNotContains(response, "핵심 키워드")

    def test_host_replies_are_short_phrases(self):
        cases = [
            ("질문 1", LABEL_YES, "그렇습니다."),
            ("질문 2", LABEL_NO, "그렇지 않습니다."),
            ("질문 3", LABEL_PARTIAL, "그럴 수도 있습니다."),
            ("질문 4", "질문이 모호합니다", "그럴 수도 있습니다."),
            ("질문 5", "관계없습니다", "관계없습니다."),
        ]
        for question, label, reply in cases:
            with self.subTest(label=label):
                response, _ = self._ask(question, QuestionJudgement(label=label))
                self.assertContains(response, reply)

    @override_settings(QUESTION_HISTORY_LIMIT=2)
    def test_recent_history_is_sent_oldest_first(self):
        for index in range(3):
            QuestionLog.objects.create(
                game_session=self.game_session, question_text=f"질문 {index}", answer_label=LABEL_NO
            )

        _, classifier = self._ask("새 질문", QuestionJudgement(label=LABEL_NO))

        history = classifier.call_args.kwargs["history"]
        self.assertEqual([question for question, _ in history], ["질문 1", "질문 2"])
        self.assertEqual(classifier.call_args.kwargs["answer_checkpoints"], CHECKPOINTS)

    def test_duplicate_question_does_not_call_ai_twice(self):
        QuestionLog.objects.create(game_session=self.game_session, question_text="남자는 수프를 먹었나요?", answer_label="맞습니다")

        _, classifier = self._ask("남자는 수프를 먹었나요?", QuestionJudgement(label=LABEL_YES))

        classifier.assert_not_called()
        self.assertEqual(self.game_session.question_logs.count(), 1)

    def test_question_length_is_limited(self):
        _, classifier = self._ask("가" * 501, QuestionJudgement(label=LABEL_YES))

        classifier.assert_not_called()
        self.assertEqual(self.game_session.question_logs.count(), 0)

    def test_ai_error_is_shown_without_creating_question_log(self):
        with patch("game.views.classify_question", side_effect=AIRefusalError(REFUSAL_MESSAGE)):
            response = self.client.post(
                reverse("game:ask_question", args=[self.game_session.id]),
                {"question_text": "남자는 수프를 먹었나요?"},
                follow=True,
            )

        self.assertContains(response, REFUSAL_MESSAGE)
        self.assertEqual(self.game_session.question_logs.count(), 0)

    def test_insufficient_final_answer_shows_matched_count(self):
        judgement = FinalAnswerJudgement(label=FINAL_ANSWER_INSUFFICIENT, met_count=2, total_count=3)
        with patch("game.views.classify_final_answer", return_value=judgement):
            response = self.client.post(
                reverse("game:submit_final_answer", args=[self.game_session.id]),
                {"submitted_answer": "남자는 조난당했다."},
                follow=True,
            )

        self.assertContains(response, FINAL_ANSWER_INSUFFICIENT)
        self.assertContains(response, "핵심 3개 중 2개를 맞혔어요.")
        self.assertContains(response, "정답에는 핵심 키워드 3개가 모두 포함되어야 합니다.")
        self.game_session.refresh_from_db()
        self.assertEqual(self.game_session.status, GameSession.STATUS_PLAYING)

    def test_correct_final_answer_clears_game(self):
        judgement = FinalAnswerJudgement(label=FINAL_ANSWER_CORRECT, met_count=3, total_count=3)
        with patch("game.views.classify_final_answer", return_value=judgement):
            response = self.client.post(
                reverse("game:submit_final_answer", args=[self.game_session.id]),
                {"submitted_answer": "정답"},
            )

        self.assertRedirects(response, reverse("game:result", args=[self.game_session.id]))

    def test_start_game_resumes_existing_session(self):
        session = self.client.session
        session.save()
        self.game_session.session_key = session.session_key
        self.game_session.save(update_fields=["session_key"])

        response = self.client.get(reverse("game:start_game", args=[self.puzzle.id]))

        self.assertRedirects(response, reverse("game:play", args=[self.game_session.id]))
        self.assertEqual(GameSession.objects.filter(puzzle=self.puzzle).count(), 1)

    def test_home_shows_active_game(self):
        session = self.client.session
        session.save()
        self.game_session.session_key = session.session_key
        self.game_session.save(update_fields=["session_key"])

        response = self.client.get(reverse("game:home"))

        self.assertContains(response, "수사 이어가기")
        self.assertContains(response, self.puzzle.title)

    def test_score_penalizes_questions_and_hints(self):
        self.game_session.hint_used_count = 2
        self.game_session.save(update_fields=["hint_used_count"])
        QuestionLog.objects.bulk_create(
            [
                QuestionLog(game_session=self.game_session, question_text="질문 1", answer_label="맞습니다"),
                QuestionLog(game_session=self.game_session, question_text="질문 2", answer_label="아닙니다"),
            ]
        )

        self.assertEqual(self.game_session.score, 660)


@override_settings(AI_CALLS_PER_MINUTE=0)
class AsyncQuestionTests(TestCase):
    """The play page sends questions with fetch and Accept: application/json."""

    def setUp(self):
        self.puzzle = Puzzle.objects.create(title="비동기 문제", scenario="s", answer_text="a")
        self.game_session = _owned_game(self.client, puzzle=self.puzzle)
        self.url = reverse("game:ask_question", args=[self.game_session.id])

    def _ask(self, question, judgement=None, **patch_kwargs):
        patch_kwargs.setdefault("return_value", judgement or QuestionJudgement(label=LABEL_YES))
        with patch("game.views.classify_question", **patch_kwargs) as classifier:
            response = self.client.post(self.url, {"question_text": question}, HTTP_ACCEPT="application/json")
        return response, classifier

    def test_success_returns_rendered_exchange(self):
        response, _ = self._ask("남자는 수프를 먹었나요?")

        data = response.json()
        self.assertTrue(data["ok"])
        self.assertEqual(data["question_count"], 1)
        self.assertIn("남자는 수프를 먹었나요?", data["html"])
        self.assertIn("그렇습니다.", data["html"])
        self.assertIn("판정이 이상해요", data["html"])
        self.assertIn("csrfmiddlewaretoken", data["html"])
        self.assertEqual(self.game_session.question_logs.count(), 1)

    def test_question_text_is_escaped_in_html(self):
        response, _ = self._ask("<script>alert(1)</script>")

        html = response.json()["html"]
        self.assertNotIn("<script>alert(1)</script>", html)
        self.assertIn("&lt;script&gt;", html)

    def test_errors_come_back_as_messages_without_logs(self):
        QuestionLog.objects.create(game_session=self.game_session, question_text="중복", answer_label=LABEL_NO)
        cases = [
            ("중복", {}, "이미 같은 질문을 했습니다."),
            ("", {}, "질문을 입력해 주세요."),
            ("가" * 501, {}, "500자 이하"),
            ("새 질문", {"side_effect": AIRefusalError(REFUSAL_MESSAGE)}, REFUSAL_MESSAGE),
        ]
        for question, patch_kwargs, message in cases:
            with self.subTest(question=question[:10]):
                response, _ = self._ask(question, **patch_kwargs)
                data = response.json()
                self.assertFalse(data["ok"])
                self.assertIn(message, data["message"])
        self.assertEqual(self.game_session.question_logs.count(), 1)

    def test_errors_do_not_leave_flash_messages_for_next_page(self):
        self._ask("", None)

        response = self.client.get(reverse("game:play", args=[self.game_session.id]))

        self.assertNotContains(response, "질문을 입력해 주세요.")

    def test_cleared_game_returns_redirect_target(self):
        self.game_session.status = GameSession.STATUS_CLEARED
        self.game_session.save(update_fields=["status"])

        response, classifier = self._ask("질문")

        classifier.assert_not_called()
        self.assertEqual(response.json()["redirect"], reverse("game:result", args=[self.game_session.id]))

    def test_play_page_marks_the_composer_for_async_submit(self):
        response = self.client.get(reverse("game:play", args=[self.game_session.id]))

        self.assertContains(response, "data-async-question")
        self.assertContains(response, "data-composer-error")


class HintTests(TestCase):
    def setUp(self):
        self.puzzle = Puzzle.objects.create(
            title="힌트 문제",
            scenario="시나리오",
            answer_text="진실",
            answer_checkpoints="\n".join(CHECKPOINTS),
            checkpoint_hints="바다 힌트\n음식 힌트\n맛 힌트",
            hint1="고정 힌트 1",
            hint2="고정 힌트 2",
        )
        self.game_session = _owned_game(self.client, puzzle=self.puzzle)

    def _use_hint(self):
        self.client.post(reverse("game:use_hint", args=[self.game_session.id]))
        self.game_session.refresh_from_db()

    def test_hint_targets_first_unrevealed_checkpoint(self):
        QuestionLog.objects.create(
            game_session=self.game_session, question_text="q", answer_label=LABEL_YES, revealed_checkpoints=[1]
        )

        self._use_hint()
        self._use_hint()

        self.assertEqual(self.game_session.revealed_hint_texts, ["음식 힌트", "맛 힌트"])
        self.assertEqual(self.game_session.hint_used_count, 2)

    def test_falls_back_to_fixed_hints_after_checkpoint_hints(self):
        QuestionLog.objects.create(
            game_session=self.game_session, question_text="q", answer_label=LABEL_YES, revealed_checkpoints=[1, 2]
        )

        self._use_hint()
        self._use_hint()

        self.assertEqual(self.game_session.revealed_hint_texts, ["맛 힌트", "고정 힌트 1"])

    def test_hint_limit_is_kept(self):
        for _ in range(5):
            self._use_hint()

        self.assertEqual(self.game_session.hint_used_count, 3)
        self.assertEqual(len(self.game_session.revealed_hint_texts), 3)

    def test_legacy_sessions_keep_showing_fixed_hints(self):
        self.game_session.hint_used_count = 1
        self.game_session.save(update_fields=["hint_used_count"])

        response = self.client.get(reverse("game:play", args=[self.game_session.id]))

        self.assertContains(response, "고정 힌트 1")


class JudgementReportTests(TestCase):
    def setUp(self):
        self.puzzle = Puzzle.objects.create(title="신고 문제", scenario="s", answer_text="a")
        self.game_session = _owned_game(self.client, puzzle=self.puzzle)
        self.log = QuestionLog.objects.create(game_session=self.game_session, question_text="이상한 판정?", answer_label=LABEL_NO)

    def test_player_can_report_a_judgement(self):
        response = self.client.post(
            reverse("game:report_judgement", args=[self.game_session.id, self.log.id]), follow=True
        )

        self.log.refresh_from_db()
        self.assertIsNotNone(self.log.reported_at)
        self.assertContains(response, "판정 신고가 접수되었어요.")
        self.assertContains(response, "신고 접수됨")

    def test_cannot_report_a_log_from_another_game(self):
        other_session = _owned_game(self.client, puzzle=self.puzzle)

        response = self.client.post(reverse("game:report_judgement", args=[other_session.id, self.log.id]))

        self.assertEqual(response.status_code, 404)

    def test_admin_action_registers_reported_question_as_test_case(self):
        admin_user = get_user_model().objects.create_superuser("admin", "admin@example.com", "pw")
        request = RequestFactory().post("/admin/")
        request.user = admin_user
        model_admin = QuestionLogAdmin(QuestionLog, AdminSite())
        model_admin.message_user = MagicMock()
        action = next(a for a in model_admin.actions if a.short_description.endswith(f"{LABEL_YES})"))

        action(model_admin, request, QuestionLog.objects.all())
        action(model_admin, request, QuestionLog.objects.all())

        test_case = QuestionTestCase.objects.get()
        self.assertEqual(test_case.expected_label, LABEL_YES)
        self.assertEqual(test_case.question_text, "이상한 판정?")
        self.assertIn(LABEL_NO, test_case.memo)


class GameOwnershipTests(TestCase):
    def setUp(self):
        self.puzzle = Puzzle.objects.create(title="소유 문제", scenario="s", answer_text="a", hint1="힌트")
        self.game_session = _owned_game(self.client, puzzle=self.puzzle)
        self.log = QuestionLog.objects.create(game_session=self.game_session, question_text="q", answer_label=LABEL_NO)

    def _other_client_requests(self):
        other = self.client_class()
        game_id = self.game_session.id
        return {
            "play": other.get(reverse("game:play", args=[game_id])),
            "result": other.get(reverse("game:result", args=[game_id])),
            "ask": other.post(reverse("game:ask_question", args=[game_id]), {"question_text": "새 질문"}),
            "hint": other.post(reverse("game:use_hint", args=[game_id])),
            "answer": other.post(reverse("game:submit_final_answer", args=[game_id]), {"submitted_answer": "답"}),
            "report": other.post(reverse("game:report_judgement", args=[game_id, self.log.id])),
        }

    def test_other_visitors_cannot_touch_someone_elses_game(self):
        with patch("game.views.classify_question") as classifier, patch("game.views.classify_final_answer") as grader:
            responses = self._other_client_requests()

        for name, response in responses.items():
            with self.subTest(view=name):
                self.assertEqual(response.status_code, 404)
        classifier.assert_not_called()
        grader.assert_not_called()
        self.game_session.refresh_from_db()
        self.assertEqual(self.game_session.hint_used_count, 0)
        self.assertEqual(self.game_session.question_logs.count(), 1)

    def test_owner_can_play(self):
        response = self.client.get(reverse("game:play", args=[self.game_session.id]))

        self.assertEqual(response.status_code, 200)

    def test_logged_in_owner_keeps_access_and_others_do_not(self):
        owner = get_user_model().objects.create_user("owner", password="pw-owner-123")
        other = get_user_model().objects.create_user("other", password="pw-other-123")
        PlayerProfile.objects.create(user=owner, nickname="owner")
        PlayerProfile.objects.create(user=other, nickname="other")
        game_session = GameSession.objects.create(puzzle=self.puzzle, user=owner)
        url = reverse("game:play", args=[game_session.id])

        self.client.force_login(owner)
        self.assertEqual(self.client.get(url).status_code, 200)

        self.client.force_login(other)
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_game_without_owner_is_not_served(self):
        orphan = GameSession.objects.create(puzzle=self.puzzle)

        self.assertEqual(self.client.get(reverse("game:play", args=[orphan.id])).status_code, 404)


class AbuseLimitTests(TestCase):
    def setUp(self):
        cache.clear()
        self.puzzle = Puzzle.objects.create(title="제한 문제", scenario="s", answer_text="a")
        self.game_session = _owned_game(self.client, puzzle=self.puzzle)

    def tearDown(self):
        cache.clear()

    def _ask(self, question):
        return self.client.post(
            reverse("game:ask_question", args=[self.game_session.id]), {"question_text": question}, follow=True
        )

    @override_settings(AI_CALLS_PER_MINUTE=2, MAX_QUESTIONS_PER_GAME=100)
    def test_questions_are_rate_limited_per_client(self):
        with patch("game.views.classify_question", return_value=QuestionJudgement(label=LABEL_NO)) as classifier:
            self._ask("질문 1")
            self._ask("질문 2")
            response = self._ask("질문 3")

        self.assertEqual(classifier.call_count, 2)
        self.assertContains(response, "요청이 너무 많아요.")
        self.assertEqual(self.game_session.question_logs.count(), 2)

    @override_settings(AI_CALLS_PER_MINUTE=1)
    def test_final_answers_share_the_rate_limit(self):
        judgement = FinalAnswerJudgement(label=FINAL_ANSWER_INSUFFICIENT)
        with patch("game.views.classify_question", return_value=QuestionJudgement(label=LABEL_NO)):
            self._ask("질문 1")
        with patch("game.views.classify_final_answer", return_value=judgement) as grader:
            response = self.client.post(
                reverse("game:submit_final_answer", args=[self.game_session.id]), {"submitted_answer": "답"}, follow=True
            )

        grader.assert_not_called()
        self.assertContains(response, "요청이 너무 많아요.")

    @override_settings(AI_CALLS_PER_MINUTE=0, MAX_QUESTIONS_PER_GAME=1)
    def test_questions_per_game_are_capped(self):
        with patch("game.views.classify_question", return_value=QuestionJudgement(label=LABEL_NO)) as classifier:
            self._ask("질문 1")
            response = self._ask("질문 2")

        self.assertEqual(classifier.call_count, 1)
        self.assertContains(response, "질문 1개를 모두 사용했어요.")

    @override_settings(AI_CALLS_PER_MINUTE=1)
    def test_duplicate_questions_do_not_use_quota(self):
        with patch("game.views.classify_question", return_value=QuestionJudgement(label=LABEL_NO)) as classifier:
            self._ask("질문 1")
            response = self._ask("질문 1")

        self.assertEqual(classifier.call_count, 1)
        self.assertContains(response, "이미 같은 질문을 했습니다.")


@override_settings(AI_CALLS_PER_MINUTE=0, DAILY_AI_BUDGET_USD=0)
class DailyLimitTests(TestCase):
    def setUp(self):
        self.puzzle = Puzzle.objects.create(title="일일 제한 문제", scenario="s", answer_text="a")

    def _ask(self, game_session, question):
        return self.client.post(
            reverse("game:ask_question", args=[game_session.id]), {"question_text": question}, follow=True
        )

    def _login(self, username="daily-player"):
        user = get_user_model().objects.create_user(username)
        PlayerProfile.objects.create(user=user, nickname=username.replace("-", "_")[:12])
        self.client.force_login(user)
        return user

    @override_settings(DAILY_AI_CALLS_PER_GUEST=2)
    def test_guest_daily_cap_spans_games_and_final_answers(self):
        first = _owned_game(self.client, puzzle=self.puzzle)
        with patch("game.views.classify_question", return_value=QuestionJudgement(label=LABEL_NO)):
            self._ask(first, "질문 1")
        second_puzzle = Puzzle.objects.create(title="두 번째", scenario="s", answer_text="a")
        second = _owned_game(self.client, puzzle=second_puzzle)
        judgement = FinalAnswerJudgement(label=FINAL_ANSWER_INSUFFICIENT)
        with patch("game.views.classify_final_answer", return_value=judgement) as grader:
            self.client.post(reverse("game:submit_final_answer", args=[second.id]), {"submitted_answer": "답"})
            response = self.client.post(
                reverse("game:submit_final_answer", args=[second.id]), {"submitted_answer": "다른 답"}, follow=True
            )

        self.assertEqual(grader.call_count, 1)
        self.assertContains(response, "오늘 쓸 수 있는 질문·정답 제출 2회를 모두 썼어요.")
        self.assertEqual(DailyUsage.objects.get().count, 2)

    @override_settings(DAILY_AI_CALLS_PER_GUEST=1, DAILY_AI_CALLS_PER_ACCOUNT=3, **GOOGLE_TEST_SETTINGS)
    def test_logged_in_players_are_counted_by_account_with_their_own_cap(self):
        user = self._login()
        game_session = GameSession.objects.create(puzzle=self.puzzle, user=user)
        with patch("game.views.classify_question", return_value=QuestionJudgement(label=LABEL_NO)) as classifier:
            for number in range(4):
                response = self._ask(game_session, f"질문 {number}")

        self.assertEqual(classifier.call_count, 3)
        self.assertContains(response, "3회를 모두 썼어요.")
        self.assertNotContains(response, "로그인하면")
        self.assertEqual(DailyUsage.objects.get().identity, f"user:{user.pk}")

    @override_settings(DAILY_AI_CALLS_PER_GUEST=1, DAILY_AI_CALLS_PER_ACCOUNT=300, **GOOGLE_TEST_SETTINGS)
    def test_guest_limit_message_suggests_login_when_available(self):
        game_session = _owned_game(self.client, puzzle=self.puzzle)
        with patch("game.views.classify_question", return_value=QuestionJudgement(label=LABEL_NO)):
            self._ask(game_session, "질문 1")
            response = self._ask(game_session, "질문 2")

        self.assertContains(response, "로그인하면 하루 300회까지 쓸 수 있어요.")

    @override_settings(DAILY_AI_CALLS_PER_GUEST=1)
    def test_daily_cap_resets_the_next_day(self):
        game_session = _owned_game(self.client, puzzle=self.puzzle)
        with patch("game.views.classify_question", return_value=QuestionJudgement(label=LABEL_NO)) as classifier:
            self._ask(game_session, "질문 1")
            DailyUsage.objects.update(day=timezone.localdate() - timedelta(days=1))
            self._ask(game_session, "질문 2")

        self.assertEqual(classifier.call_count, 2)

    @override_settings(DAILY_AI_BUDGET_USD=1.0, AI_PRICE_INPUT_PER_MTOK=2, AI_PRICE_OUTPUT_PER_MTOK=10,
                       AI_PRICE_CACHE_WRITE_PER_MTOK=2.5, AI_PRICE_CACHE_READ_PER_MTOK=0.1)
    def test_budget_stop_uses_todays_estimated_cost(self):
        game_session = _owned_game(self.client, puzzle=self.puzzle)
        # $0.20 input + $0.70 output + $0.025 cache write + $0.01 cache read = $0.935 today.
        AIUsageLog.objects.create(operation="question", model="m", input_tokens=100_000, output_tokens=70_000,
                                  cache_creation_input_tokens=10_000, cache_read_input_tokens=100_000)
        old = AIUsageLog.objects.create(operation="question", model="m", output_tokens=1_000_000)
        AIUsageLog.objects.filter(pk=old.pk).update(created_at=timezone.now() - timedelta(days=1))
        self.assertAlmostEqual(estimated_cost_usd(), 0.935)

        with patch("game.views.classify_question", return_value=QuestionJudgement(label=LABEL_NO)) as classifier:
            self._ask(game_session, "질문 1")
            AIUsageLog.objects.create(operation="question", model="m", output_tokens=10_000)
            response = self._ask(game_session, "질문 2")

        self.assertEqual(classifier.call_count, 1)
        self.assertContains(response, "오늘 준비한 진행자 이용량이 모두 소진됐어요.")

    @override_settings(DAILY_AI_BUDGET_USD=0.01)
    def test_admin_usage_list_shows_todays_estimate(self):
        admin_user = get_user_model().objects.create_superuser("boss", password=None)
        self.client.force_login(admin_user)

        response = self.client.get(reverse("admin:game_aiusagelog_changelist"))

        self.assertContains(response, "오늘 예상 사용액: $0.0000 (하루 예산 $0.01")


@override_settings(AI_CALLS_PER_MINUTE=0, DAILY_AI_BUDGET_USD=0)
class RankingTests(TestCase):
    def setUp(self):
        self.puzzle = Puzzle.objects.create(title="순위 문제", scenario="s", answer_text="진실")
        self.other_puzzle = Puzzle.objects.create(title="두 번째 순위 문제", scenario="s", answer_text="진실")

    def _player(self, nickname, email=None):
        user = get_user_model().objects.create_user(f"user-{nickname}", email=email or f"{nickname}@example.com")
        PlayerProfile.objects.create(user=user, nickname=nickname)
        return user

    def _ranked(self, user, puzzle, score, seconds, cleared_minutes_ago=0):
        cleared_at = timezone.now() - timedelta(minutes=cleared_minutes_ago)
        return GameSession.objects.create(
            puzzle=puzzle, user=user, status=GameSession.STATUS_CLEARED, cleared_at=cleared_at,
            final_score=score, play_seconds=seconds, is_ranked=True,
        )

    def _solve(self, game_session):
        judgement = FinalAnswerJudgement(label=FINAL_ANSWER_CORRECT)
        with patch("game.views.classify_final_answer", return_value=judgement):
            return self.client.post(
                reverse("game:submit_final_answer", args=[game_session.id]), {"submitted_answer": "답"}, follow=True
            )

    def test_first_clear_is_ranked_and_replay_is_practice(self):
        user = self._player("첫클리어")
        self.client.force_login(user)
        first = GameSession.objects.create(puzzle=self.puzzle, user=user)
        QuestionLog.objects.create(game_session=first, question_text="q", answer_label=LABEL_NO)

        response = self._solve(first)
        first.refresh_from_db()
        self.assertTrue(first.is_ranked)
        self.assertEqual(first.final_score, 980)
        self.assertContains(response, "이번 기록은 이 문제 <strong>1위</strong>예요.")

        replay = GameSession.objects.create(puzzle=self.puzzle, user=user)
        response = self._solve(replay)
        replay.refresh_from_db()
        self.assertFalse(replay.is_ranked)
        self.assertEqual(replay.final_score, 1000)
        self.assertContains(response, "연습 기록이라 순위에는 반영되지 않아요.")
        self.assertEqual(GameSession.objects.filter(user=user, is_ranked=True).count(), 1)

    def test_one_ranked_clear_per_account_and_puzzle_is_enforced(self):
        from django.db import IntegrityError, transaction

        user = self._player("중복")
        self._ranked(user, self.puzzle, 900, 60)
        with self.assertRaises(IntegrityError), transaction.atomic():
            self._ranked(user, self.puzzle, 1000, 30)

    @override_settings(**GOOGLE_TEST_SETTINGS)
    def test_guest_clear_shows_login_prompt_and_counts_after_login(self):
        from .accounts import claim_guest_games

        game_session = _owned_game(self.client, puzzle=self.puzzle)
        response = self._solve(game_session)
        self.assertContains(response, "구글로 로그인하면 이 기록으로 순위에 오를 수 있어요.")
        game_session.refresh_from_db()
        self.assertFalse(game_session.is_ranked)

        user = self._player("게스트출신")
        claim_guest_games(user, game_session.session_key)

        game_session.refresh_from_db()
        self.assertTrue(game_session.is_ranked)

    def test_claimed_guest_clear_stays_practice_when_account_already_ranked(self):
        from .accounts import claim_guest_games

        user = self._player("이미순위")
        ranked = self._ranked(user, self.puzzle, 700, 300)
        guest_game = _owned_game(self.client, puzzle=self.puzzle)
        guest_game.mark_cleared("답")

        claim_guest_games(user, guest_game.session_key)

        guest_game.refresh_from_db()
        self.assertFalse(guest_game.is_ranked)
        self.assertEqual(list(GameSession.objects.filter(is_ranked=True)), [ranked])

    def test_puzzle_ranking_orders_by_score_then_time_then_clear_date(self):
        slow = self._ranked(self._player("느림"), self.puzzle, 900, 600, cleared_minutes_ago=50)
        fast = self._ranked(self._player("빠름"), self.puzzle, 900, 120, cleared_minutes_ago=10)
        early = self._ranked(self._player("먼저"), self.puzzle, 900, 120, cleared_minutes_ago=40)
        best = self._ranked(self._player("최고"), self.puzzle, 980, 900)

        self.assertEqual(puzzle_ranking(self.puzzle), [best, early, fast, slow])

        response = self.client.get(reverse("game:puzzle_ranking", args=[self.puzzle.id]))
        content = response.content.decode()
        self.assertLess(content.index("최고"), content.index("먼저"))
        self.assertContains(response, "2분 0초")

    def test_overall_ranking_sums_first_clears_and_shows_only_nicknames(self):
        alice = self._player("앨리스", email="alice-secret@example.com")
        bob = self._player("밥")
        self._ranked(alice, self.puzzle, 800, 60)
        self._ranked(alice, self.other_puzzle, 700, 60)
        self._ranked(bob, self.puzzle, 1000, 60)
        GameSession.objects.create(puzzle=self.other_puzzle, user=bob, status=GameSession.STATUS_CLEARED,
                                   cleared_at=timezone.now(), final_score=1000, play_seconds=5)
        staff = get_user_model().objects.create_user("staff-no-profile", is_staff=True)
        GameSession.objects.create(puzzle=self.puzzle, user=staff, status=GameSession.STATUS_CLEARED,
                                   cleared_at=timezone.now(), final_score=1000, play_seconds=5, is_ranked=True)

        rows = overall_ranking()
        self.assertEqual([(row.nickname, row.total_score, row.cleared_count) for row in rows],
                         [("앨리스", 1500, 2), ("밥", 1000, 1)])

        response = self.client.get(reverse("game:ranking"))
        self.assertContains(response, "1500점")
        self.assertNotContains(response, "alice-secret")
        self.assertNotContains(response, "staff-no-profile")

    def test_inactive_puzzles_leave_the_boards(self):
        user = self._player("숨김")
        self._ranked(user, self.puzzle, 900, 60)
        self.puzzle.is_active = False
        self.puzzle.save()

        self.assertEqual(overall_ranking(), [])
        self.assertEqual(self.client.get(reverse("game:puzzle_ranking", args=[self.puzzle.id])).status_code, 404)

    def test_viewer_below_the_board_still_sees_their_row(self):
        from . import ranking_views

        players = [self._player(f"p{number}") for number in range(4)]
        for number, player in enumerate(players):
            self._ranked(player, self.puzzle, 1000 - number * 10, 60)
        self.client.force_login(players[-1])

        with patch.object(ranking_views, "RANKING_SIZE", 2):
            response = self.client.get(reverse("game:puzzle_ranking", args=[self.puzzle.id]))

        self.assertContains(response, "p0")
        self.assertNotContains(response, ">p2<")
        self.assertContains(response, "p3 (나)")
        self.assertEqual([entry["rank"] for entry in response.context["entries"]], [1, 2])
        self.assertEqual(response.context["mine_below"]["rank"], 4)

    def test_backfill_ranks_each_accounts_first_existing_clear(self):
        import importlib
        from django.apps import apps as django_apps

        migration = importlib.import_module("game.migrations.0014_ranked_first_clears")
        user = self._player("예전기록")
        older = GameSession.objects.create(puzzle=self.puzzle, user=user, status=GameSession.STATUS_CLEARED,
                                           cleared_at=timezone.now() - timedelta(days=2), hint_used_count=1)
        QuestionLog.objects.create(game_session=older, question_text="q", answer_label=LABEL_NO)
        newer = GameSession.objects.create(puzzle=self.puzzle, user=user, status=GameSession.STATUS_CLEARED,
                                           cleared_at=timezone.now())
        guest = GameSession.objects.create(puzzle=self.puzzle, session_key="guest", status=GameSession.STATUS_CLEARED,
                                           cleared_at=timezone.now())

        migration.backfill_scores_and_ranks(django_apps, None)

        older.refresh_from_db(); newer.refresh_from_db(); guest.refresh_from_db()
        self.assertEqual((older.is_ranked, older.final_score), (True, 830))
        self.assertEqual((newer.is_ranked, newer.final_score), (False, 1000))
        self.assertFalse(guest.is_ranked)


class StarterFixtureTests(TestCase):
    fixtures = ["starter_puzzles"]

    def test_starter_fixture_loads_puzzle_and_test_questions(self):
        puzzle = Puzzle.objects.get()

        self.assertTrue(puzzle.is_active)
        self.assertEqual(len(puzzle.get_answer_checkpoints()), 3)
        self.assertEqual(puzzle.question_test_cases.count(), 6)
        self.assertFalse(puzzle.question_test_cases.filter(last_run_at__isnull=False).exists())
        self.assertEqual(puzzle.title, "바다거북스프")
        self.assertEqual(len(puzzle.get_checkpoint_hints()), 3)


GENERATED_CRITERIA = {
    "answer_checkpoints": ["새 체크포인트 1", "새 체크포인트 2"],
    "checkpoint_hints": ["새 힌트 1", "새 힌트 2"],
    "question_yes_facts": ["새 맞음"],
    "question_no_facts": ["새 아님"],
    "question_irrelevant_facts": ["새 무관"],
    "question_ambiguous_examples": ["새 모호"],
}


class AdminCriteriaGenerationTests(TestCase):
    def setUp(self):
        self.admin_user = get_user_model().objects.create_superuser("staff", "staff@example.com", "pw-staff-123")
        self.client.force_login(self.admin_user)
        self.puzzle = Puzzle.objects.create(
            title="기준 문제",
            scenario="s",
            answer_text="a",
            answer_checkpoints="직접 쓴 체크포인트",
            question_yes_facts="직접 다듬은 맞음 기준",
        )
        self.url = reverse("admin:game_puzzle_generate_ai_criteria", args=[self.puzzle.id])

    def _post(self, mode):
        with patch("game.admin.generate_puzzle_criteria", return_value=GENERATED_CRITERIA) as generator:
            response = self.client.post(self.url, {"mode": mode}, follow=True)
        self.puzzle.refresh_from_db()
        return response, generator

    def test_get_shows_confirmation_without_calling_claude(self):
        with patch("game.admin.generate_puzzle_criteria") as generator:
            response = self.client.get(self.url)

        generator.assert_not_called()
        self.assertContains(response, "빈 칸만 채우기")
        self.assertContains(response, "모두 덮어쓰기")
        self.assertContains(response, "정답 체크포인트")

    def test_fill_empty_keeps_hand_edited_fields(self):
        _, generator = self._post("fill_empty")

        generator.assert_called_once()
        self.assertEqual(self.puzzle.answer_checkpoints, "직접 쓴 체크포인트")
        self.assertEqual(self.puzzle.question_yes_facts, "직접 다듬은 맞음 기준")
        self.assertEqual(self.puzzle.question_no_facts, "새 아님")
        self.assertEqual(self.puzzle.question_ambiguous_examples, "새 모호")
        # Hints must stay aligned with the existing checkpoints, so they are not generated here.
        self.assertEqual(self.puzzle.checkpoint_hints, "")

    def test_fill_empty_writes_hints_with_new_checkpoints(self):
        self.puzzle.answer_checkpoints = ""
        self.puzzle.save()

        self._post("fill_empty")

        self.assertEqual(self.puzzle.get_answer_checkpoints(), ["새 체크포인트 1", "새 체크포인트 2"])
        self.assertEqual(self.puzzle.get_checkpoint_hints(), ["새 힌트 1", "새 힌트 2"])
        self.assertEqual(self.puzzle.question_yes_facts, "직접 다듬은 맞음 기준")

    def test_overwrite_replaces_everything(self):
        response, _ = self._post("overwrite")

        self.assertEqual(self.puzzle.answer_checkpoints, "새 체크포인트 1\n새 체크포인트 2")
        self.assertEqual(self.puzzle.question_yes_facts, "새 맞음")
        self.assertEqual(self.puzzle.checkpoint_hints, "새 힌트 1\n새 힌트 2")
        self.assertContains(response, "AI 판정 기준을 채웠습니다")

    def test_fill_empty_skips_billed_call_when_nothing_is_empty(self):
        for field in ("question_no_facts", "question_irrelevant_facts", "question_ambiguous_examples"):
            setattr(self.puzzle, field, "직접 작성")
        self.puzzle.save()

        response, generator = self._post("fill_empty")

        generator.assert_not_called()
        self.assertContains(response, "비어 있는 판정 기준이 없어")

    def test_bulk_action_only_fills_empty_fields(self):
        with patch("game.admin.generate_puzzle_criteria", return_value=GENERATED_CRITERIA):
            self.client.post(
                reverse("admin:game_puzzle_changelist"),
                {"action": "generate_ai_criteria", "_selected_action": [self.puzzle.id]},
            )
        self.puzzle.refresh_from_db()

        self.assertEqual(self.puzzle.question_yes_facts, "직접 다듬은 맞음 기준")
        self.assertEqual(self.puzzle.question_no_facts, "새 아님")


class AdminQuestionTestRunTests(TestCase):
    def setUp(self):
        admin_user = get_user_model().objects.create_superuser("runner", "runner@example.com", "pw-runner-123")
        self.client.force_login(admin_user)
        self.puzzle = Puzzle.objects.create(title="테스트 실행 문제", scenario="s", answer_text="a")
        QuestionTestCase.objects.create(puzzle=self.puzzle, question_text="q1", expected_label=LABEL_YES)
        QuestionTestCase.objects.create(puzzle=self.puzzle, question_text="q2", expected_label=LABEL_NO)
        self.url = reverse("admin:game_puzzle_run_question_tests", args=[self.puzzle.id])

    def test_get_shows_confirmation_without_calling_claude(self):
        with patch("game.admin.classify_question") as classifier:
            response = self.client.get(self.url)

        classifier.assert_not_called()
        self.assertContains(response, "테스트 2개 실행")

    def test_post_runs_tests_and_reports_pass_count(self):
        with patch("game.admin.classify_question", return_value=QuestionJudgement(label=LABEL_YES)) as classifier:
            response = self.client.post(self.url, follow=True)

        self.assertEqual(classifier.call_count, 2)
        self.assertContains(response, "테스트 질문 1/2개가 통과했습니다.")


class ReplyFilterTests(TestCase):
    def test_host_reply_and_class_for_every_label(self):
        from game.templatetags.game_extras import host_reply, reply_class

        cases = {
            LABEL_YES: ("그렇습니다.", "yes"),
            LABEL_NO: ("그렇지 않습니다.", "no"),
            LABEL_PARTIAL: ("그럴 수도 있습니다.", "maybe"),
            "질문이 모호합니다": ("그럴 수도 있습니다.", "maybe"),
            "관계없습니다": ("관계없습니다.", "irrelevant"),
        }
        for label, (reply, css) in cases.items():
            with self.subTest(label=label):
                self.assertEqual(host_reply(label), reply)
                self.assertEqual(reply_class(label), css)


class ResultAndHomeTests(TestCase):
    def setUp(self):
        self.puzzle = Puzzle.objects.create(title="결과 문제", scenario="s", answer_text="진실")

    def test_result_page_replays_questions_with_short_replies(self):
        game_session = _owned_game(self.client, puzzle=self.puzzle, status=GameSession.STATUS_CLEARED)
        QuestionLog.objects.create(game_session=game_session, question_text="첫 질문", answer_label=LABEL_YES)
        QuestionLog.objects.create(game_session=game_session, question_text="둘째 질문", answer_label=LABEL_PARTIAL)

        response = self.client.get(reverse("game:result", args=[game_session.id]))

        self.assertContains(response, "질문 기록")
        content = response.content.decode()
        self.assertLess(content.index("첫 질문"), content.index("둘째 질문"))
        self.assertContains(response, "그렇습니다.")
        self.assertContains(response, "그럴 수도 있습니다.")
        self.assertNotContains(response, "판정이 이상해요")

    def test_result_page_without_questions(self):
        game_session = _owned_game(self.client, puzzle=self.puzzle, status=GameSession.STATUS_CLEARED)

        response = self.client.get(reverse("game:result", args=[game_session.id]))

        self.assertContains(response, "질문 없이 정답을 맞혔어요.")

    def test_home_marks_cleared_puzzles_with_best_score(self):
        best = _owned_game(self.client, puzzle=self.puzzle, status=GameSession.STATUS_CLEARED)
        worse = _owned_game(self.client, puzzle=self.puzzle, status=GameSession.STATUS_CLEARED, hint_used_count=2)
        QuestionLog.objects.create(game_session=worse, question_text="q", answer_label=LABEL_NO)
        self.assertGreater(best.score, worse.score)

        response = self.client.get(reverse("game:home"))

        self.assertContains(response, f"해결 · 최고 {best.score}점")
        self.assertContains(response, "다시 수사")

    def test_home_ignores_other_visitors_clears(self):
        GameSession.objects.create(puzzle=self.puzzle, session_key="someone-else", status=GameSession.STATUS_CLEARED)

        response = self.client.get(reverse("game:home"))

        self.assertNotContains(response, "해결 ·")
        self.assertContains(response, "수사 시작")

    def test_pages_link_the_site_icon(self):
        response = self.client.get(reverse("game:home"))

        self.assertContains(response, "game/img/favicon.svg")

    def test_play_page_uses_text_wordmark_and_stamps_without_mascot_images(self):
        game_session = _owned_game(self.client, puzzle=self.puzzle)
        QuestionLog.objects.create(game_session=game_session, question_text="q", answer_label=LABEL_YES)

        response = self.client.get(reverse("game:play", args=[game_session.id]))

        self.assertContains(response, 'class="brand-name"')
        self.assertContains(response, 'class="message-bubble host judgement yes"')
        for image in ("avatar", "game-logo", ".png"):
            self.assertNotContains(response, image)


class PuzzleTransferCommandTests(TestCase):
    fixtures = ["starter_puzzles"]

    def setUp(self):
        import tempfile

        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = f"{self.tmp.name}/private/puzzles.json"
        self.custom = Puzzle.objects.create(
            title="비공개 문제",
            scenario="상황",
            answer_text="진실",
            answer_checkpoints="c1\nc2",
            checkpoint_hints="h1\nh2",
            hint1="고정 힌트",
            is_active=True,
        )
        QuestionTestCase.objects.create(puzzle=self.custom, question_text="질문?", expected_label=LABEL_YES, memo="m")

    def _call(self, *args):
        from io import StringIO

        from django.core.management import call_command

        out = StringIO()
        call_command(*args, stdout=out)
        return out.getvalue()

    def test_export_excluding_starter_writes_only_new_puzzles(self):
        self._call("export_puzzles", self.path, "--exclude-starter")

        data = json.load(open(self.path, encoding="utf-8"))
        self.assertEqual([p["title"] for p in data["puzzles"]], ["비공개 문제"])
        self.assertEqual(data["puzzles"][0]["answer_text"], "진실")
        self.assertEqual(data["puzzles"][0]["test_cases"][0]["question_text"], "질문?")

    def test_round_trip_into_a_database_with_other_ids(self):
        self._call("export_puzzles", self.path, "--exclude-starter")
        self.custom.delete()
        Puzzle.objects.create(title="다른 문제", scenario="s", answer_text="a")  # takes the next id

        out = self._call("import_puzzles", self.path)

        puzzle = Puzzle.objects.get(title="비공개 문제")
        self.assertEqual(puzzle.get_checkpoint_hints(), ["h1", "h2"])
        self.assertTrue(puzzle.is_active)
        self.assertEqual(puzzle.question_test_cases.get().memo, "m")
        self.assertIn("1 new", out)

    def test_import_twice_updates_instead_of_duplicating(self):
        self._call("export_puzzles", self.path, "--exclude-starter")
        self.custom.answer_text = "바뀐 진실"
        self.custom.save()

        self._call("import_puzzles", self.path)

        self.assertEqual(Puzzle.objects.filter(title="비공개 문제").count(), 1)
        self.assertEqual(Puzzle.objects.get(title="비공개 문제").answer_text, "진실")
        self.assertEqual(QuestionTestCase.objects.filter(puzzle__title="비공개 문제").count(), 1)

    def test_dry_run_saves_nothing(self):
        self._call("export_puzzles", self.path, "--exclude-starter")
        self.custom.delete()

        out = self._call("import_puzzles", self.path, "--dry-run")

        self.assertIn("Dry run", out)
        self.assertFalse(Puzzle.objects.filter(title="비공개 문제").exists())

    def test_rejects_bad_files(self):
        from django.core.management.base import CommandError

        with open(self.path.replace("/private/puzzles.json", "/bad.json"), "w", encoding="utf-8") as handle:
            json.dump({"version": 99, "puzzles": []}, handle)

        with self.assertRaises(CommandError):
            self._call("import_puzzles", self.path.replace("/private/puzzles.json", "/bad.json"))
        with self.assertRaises(CommandError):
            self._call("import_puzzles", f"{self.tmp.name}/missing.json")


class AccountTests(TestCase):
    def setUp(self):
        self.puzzle = Puzzle.objects.create(title="계정 문제", scenario="s", answer_text="a")
        self.user = get_user_model().objects.create_user("google-user", email="player@example.com")

    def _with_profile(self, nickname="추리왕"):
        PlayerProfile.objects.create(user=self.user, nickname=nickname)

    # Login button -------------------------------------------------------
    @override_settings(GOOGLE_LOGIN_ENABLED=False)
    def test_login_button_hidden_without_google_keys(self):
        response = self.client.get(reverse("game:home"))

        self.assertNotContains(response, "Google로 로그인")
        self.assertContains(response, "개인정보 처리방침")

    @override_settings(**GOOGLE_TEST_SETTINGS)
    def test_login_button_posts_to_google_provider(self):
        response = self.client.get(reverse("game:home"))

        self.assertContains(response, "Google로 로그인")
        self.assertContains(response, "/accounts/google/login/")

    # Guest games move to the account -------------------------------------
    def test_login_claims_games_from_the_guest_session(self):
        from django.contrib.auth import login
        from django.contrib.sessions.backends.db import SessionStore

        self.client.get(reverse("game:start_game", args=[self.puzzle.id]))
        guest_game = GameSession.objects.get()
        self.assertIsNone(guest_game.user)
        other_guest = GameSession.objects.create(puzzle=self.puzzle, session_key="someone-else")

        request = RequestFactory().get("/")
        request.session = SessionStore(session_key=self.client.session.session_key)
        login(request, self.user, backend="django.contrib.auth.backends.ModelBackend")

        guest_game.refresh_from_db()
        other_guest.refresh_from_db()
        self.assertEqual(guest_game.user, self.user)
        self.assertIsNone(other_guest.user)

    def test_claimed_game_is_reachable_after_login(self):
        from game.accounts import claim_guest_games

        game_session = _owned_game(self.client, puzzle=self.puzzle)
        claim_guest_games(self.user, game_session.session_key)
        self._with_profile()
        self.client.force_login(self.user)

        response = self.client.get(reverse("game:play", args=[game_session.id]))

        self.assertEqual(response.status_code, 200)

    # Nickname required ------------------------------------------------------
    def test_logged_in_player_without_nickname_is_sent_to_nickname_page(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("game:home"))

        self.assertRedirects(response, f"{reverse('game:nickname')}?next=/")

    def test_json_requests_get_a_redirect_target_instead(self):
        game_session = GameSession.objects.create(puzzle=self.puzzle, user=self.user)
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("game:ask_question", args=[game_session.id]),
            {"question_text": "q"},
            HTTP_ACCEPT="application/json",
        )

        self.assertTrue(response.json()["redirect"].startswith(reverse("game:nickname")))

    def test_staff_are_not_forced_to_pick_a_nickname(self):
        staff = get_user_model().objects.create_user("staff-user", is_staff=True)
        self.client.force_login(staff)

        self.assertEqual(self.client.get(reverse("game:home")).status_code, 200)

    def test_nickname_rules(self):
        PlayerProfile.objects.create(
            user=get_user_model().objects.create_user("other"), nickname="Taken"
        )
        self.client.force_login(self.user)
        cases = {
            "a": "2~12자",
            "공백 있는 이름": "2~12자",
            "<b>굵게</b>": "2~12자",
            "관리자": "쓸 수 없는",
            "taken": "이미 다른 사람이",
        }
        for nickname, error in cases.items():
            with self.subTest(nickname=nickname):
                response = self.client.post(reverse("game:nickname"), {"nickname": nickname})
                self.assertContains(response, error)
        self.assertFalse(PlayerProfile.objects.filter(user=self.user).exists())

    def test_valid_nickname_is_saved_and_follows_safe_next_only(self):
        self.client.force_login(self.user)

        response = self.client.post(reverse("game:nickname"), {"nickname": "추리왕_1", "next": "/play/start/1/"})
        self.assertRedirects(response, "/play/start/1/", fetch_redirect_response=False)
        self.assertEqual(self.user.player_profile.nickname, "추리왕_1")

        response = self.client.post(reverse("game:nickname"), {"nickname": "추리왕_2", "next": "https://evil.example/"})
        self.assertRedirects(response, reverse("game:home"), fetch_redirect_response=False)
        self.user.player_profile.refresh_from_db()
        self.assertEqual(self.user.player_profile.nickname, "추리왕_2")

    def test_header_shows_nickname_but_never_the_email(self):
        self._with_profile()
        self.client.force_login(self.user)

        response = self.client.get(reverse("game:home"))

        self.assertContains(response, "추리왕")
        self.assertContains(response, "로그아웃")
        self.assertNotContains(response, "player@example.com")

    def test_logout_is_post_and_ends_the_session(self):
        self._with_profile()
        self.client.force_login(self.user)

        self.client.post(reverse("account_logout"))

        self.assertNotIn("_auth_user_id", self.client.session)

    def test_allauth_pages_use_the_site_layout(self):
        self._with_profile()
        self.client.force_login(self.user)

        response = self.client.get(reverse("account_logout"))

        self.assertContains(response, 'class="brand-name"')
        self.assertContains(response, "개인정보 처리방침")
        self.assertNotContains(response, "Menu:")

    def test_email_conflict_signup_page_explains_instead_of_asking_username(self):
        from django.contrib.auth.models import AnonymousUser
        from django.template.loader import render_to_string
        from django.test import RequestFactory

        request = RequestFactory().get("/accounts/3rdparty/signup/")
        request.user = AnonymousUser()

        html = render_to_string("socialaccount/signup.html", request=request)

        self.assertIn("로그인할 수 없어요", html)
        self.assertNotIn('name="username"', html)

    # Privacy and deletion ------------------------------------------------
    def test_privacy_page_is_public(self):
        response = self.client.get(reverse("game:privacy"))

        self.assertContains(response, "수집하는 정보")

    def test_account_deletion_requires_confirmation_and_removes_records(self):
        self._with_profile()
        game_session = GameSession.objects.create(puzzle=self.puzzle, user=self.user)
        QuestionLog.objects.create(game_session=game_session, question_text="q", answer_label=LABEL_NO)
        self.client.force_login(self.user)

        self.client.post(reverse("game:delete_account"), {"confirm": "아니요"})
        self.assertTrue(get_user_model().objects.filter(pk=self.user.pk).exists())

        response = self.client.post(reverse("game:delete_account"), {"confirm": "계정 삭제"}, follow=True)

        self.assertFalse(get_user_model().objects.filter(pk=self.user.pk).exists())
        self.assertFalse(PlayerProfile.objects.exists())
        self.assertFalse(GameSession.objects.filter(pk=game_session.pk).exists())
        self.assertFalse(QuestionLog.objects.exists())
        self.assertContains(response, "계정과 플레이 기록을 삭제했어요.")
        self.assertNotIn("_auth_user_id", self.client.session)


class AIUsageLogTests(TestCase):
    def test_records_token_usage_without_prompt_content(self):
        response = SimpleNamespace(usage=SimpleNamespace(input_tokens=10, output_tokens=5), model="claude-opus-5-5")

        _record_ai_usage("question_classification", response=response)

        log = AIUsageLog.objects.get()
        self.assertEqual(log.input_tokens, 10)
        self.assertEqual(log.output_tokens, 5)
        self.assertEqual(log.total_tokens, 15)
        self.assertEqual(log.model, "claude-opus-5-5")
        self.assertTrue(log.success)

    def test_records_cached_prompt_tokens(self):
        usage = SimpleNamespace(
            input_tokens=50, cache_creation_input_tokens=0, cache_read_input_tokens=1705, output_tokens=26
        )

        _record_ai_usage("question_classification", response=SimpleNamespace(usage=usage, model="claude-sonnet-5-5"))

        log = AIUsageLog.objects.get()
        self.assertEqual(log.cache_read_input_tokens, 1705)
        self.assertEqual(log.cache_creation_input_tokens, 0)
        self.assertEqual(log.total_tokens, 50 + 1705 + 26)

    @override_settings(ANTHROPIC_API_KEY="secret-test-key")
    def test_redacts_api_key_from_error_log(self):
        _record_ai_usage("question_classification", error_message="failed with secret-test-key")

        self.assertEqual(AIUsageLog.objects.get().error_message, "failed with [redacted]")


@tag("claude_api")
class ClaudeIntegrationTests(TestCase):
    """Real, billed Claude API calls. Run with: manage.py test game --tag=claude_api"""

    SCENARIO = "남자가 식당에서 바다거북스프를 먹고 집에 돌아가 자살했다."
    ANSWER = "과거 조난 때 인육 수프를 먹었고, 식당의 진짜 바다거북스프 맛으로 진실을 깨달았다."

    def test_claude_question_classifier_returns_expected_label(self):
        judgement = classify_question(
            scenario=self.SCENARIO,
            answer_text=self.ANSWER,
            question_text="남자는 식당에서 수프를 먹었나요?",
            answer_checkpoints=CHECKPOINTS,
        )

        self.assertEqual(judgement.label, LABEL_YES)

    def test_claude_final_answer_classifier_returns_expected_label(self):
        judgement = classify_final_answer(
            scenario=self.SCENARIO,
            answer_text=self.ANSWER,
            answer_checkpoints=CHECKPOINTS,
            submitted_answer=(
                "남자는 과거 조난 상황에서 수프를 먹었는데 그건 인육 수프였다. "
                "식당에서 진짜 바다거북스프를 먹고 그 진실을 깨달았다."
            ),
        )

        self.assertEqual(judgement.label, FINAL_ANSWER_CORRECT)

    def test_claude_generates_puzzle_criteria(self):
        criteria = generate_puzzle_criteria(scenario=self.SCENARIO, answer_text=self.ANSWER)

        self.assertTrue(criteria["answer_checkpoints"])
        self.assertEqual(len(criteria["checkpoint_hints"]), len(criteria["answer_checkpoints"]))
        self.assertTrue(criteria["question_no_facts"])
