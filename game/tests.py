from unittest.mock import patch

from django.test import TestCase, override_settings
from django.urls import reverse

from .models import GameSession, OpenAIUsageLog, Puzzle, QuestionLog, QuestionTestCase
from .services import (
    FINAL_ANSWER_CORRECT,
    FINAL_ANSWER_INSUFFICIENT,
    _classify_final_answer_locally,
    _classify_question_locally,
    _classify_question_with_criteria,
    _generate_puzzle_criteria_locally,
    _normalize_label,
    _record_openai_usage,
    _validate_final_answer_api_label,
    _validate_question_api_label,
    OpenAIServiceError,
    classify_final_answer,
    classify_question,
    generate_puzzle_criteria,
)


class QuestionClassifierTests(TestCase):
    def test_normalize_label_strips_extra_text(self):
        self.assertEqual(_normalize_label("맞습니다."), "맞습니다")
        self.assertEqual(_normalize_label("결과: 관계없습니다"), "관계없습니다")
        self.assertEqual(_normalize_label("unknown"), "질문이 모호합니다")

    def test_invalid_openai_labels_raise_service_error(self):
        with self.assertRaises(OpenAIServiceError):
            _validate_question_api_label("설명만 있는 응답")
        with self.assertRaises(OpenAIServiceError):
            _validate_final_answer_api_label("판단할 수 없음")

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
        checkpoints = [
            "남자는 과거 조난 상황에서 수프를 먹었다.",
            "그때 먹은 수프는 바다거북스프가 아니라 인육 수프였다.",
            "식당에서 진짜 바다거북스프를 먹고 과거의 진실을 깨달았다.",
        ]

        self.assertEqual(
            _classify_final_answer_locally(
                "남자는 예전에 조난당했을 때 먹은 수프가 인육이었고, 식당에서 진짜 바다거북스프를 먹고 그 사실을 깨달았다.",
                checkpoints,
            ),
            FINAL_ANSWER_CORRECT,
        )
        self.assertEqual(
            _classify_final_answer_locally("남자는 예전에 조난당했고 식당에서 수프를 먹었다.", checkpoints),
            FINAL_ANSWER_INSUFFICIENT,
        )

    def test_question_criteria_override_keyword_fallback(self):
        criteria = {
            "yes": ["남자는 집에 돌아온 뒤 자살했다."],
            "no": ["남자는 원래 자살 계획이 있었다."],
            "irrelevant": ["남자의 신발 색깔"],
            "ambiguous": ["남자는 이상한 기분이 들었나요?"],
        }

        self.assertEqual(
            _classify_question_with_criteria("남자는 원래 자살 계획이 있었나요?", criteria),
            "아닙니다",
        )
        self.assertEqual(
            _classify_question_with_criteria("남자는 집에 돌아온 뒤 자살했나요?", criteria),
            "맞습니다",
        )

    def test_generate_puzzle_criteria_local_fallback(self):
        criteria = _generate_puzzle_criteria_locally(
            "한 남자가 식당에서 바다거북스프를 먹고 집에 돌아온 뒤 자살했다.",
            "그는 과거 조난 상황에서 먹었던 수프가 인육 수프였다는 사실을 깨달았다.",
        )

        self.assertIn("남자는 원래 자살 계획이 있었다.", criteria["question_no_facts"])
        self.assertTrue(criteria["answer_checkpoints"])

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


class GameFlowTests(TestCase):
    def setUp(self):
        self.puzzle = Puzzle.objects.create(
            title="테스트 문제",
            scenario="남자가 식당에서 수프를 먹고 집에 돌아갔다.",
            answer_text="남자는 수프를 먹고 과거의 진실을 깨달았다.",
        )
        self.game_session = GameSession.objects.create(puzzle=self.puzzle, status=GameSession.STATUS_PLAYING)

    def test_result_page_redirects_until_session_is_cleared(self):
        response = self.client.get(reverse("game:result", args=[self.game_session.id]))

        self.assertRedirects(response, reverse("game:play", args=[self.game_session.id]))

    def test_result_page_is_available_after_session_is_cleared(self):
        puzzle = Puzzle.objects.create(
            title="테스트 문제",
            scenario="남자가 식당에서 수프를 먹고 집에 돌아갔다.",
            answer_text="남자는 수프를 먹고 과거의 진실을 깨달았다.",
        )
        game_session = GameSession.objects.create(puzzle=puzzle, status=GameSession.STATUS_CLEARED)

        response = self.client.get(reverse("game:result", args=[game_session.id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, puzzle.answer_text)
        self.assertContains(response, "1000")

    def test_duplicate_question_does_not_call_openai_twice(self):
        QuestionLog.objects.create(
            game_session=self.game_session,
            question_text="남자는 수프를 먹었나요?",
            answer_label="맞습니다",
        )

        with patch("game.views.classify_question") as classifier:
            self.client.post(
                reverse("game:ask_question", args=[self.game_session.id]),
                {"question_text": "남자는 수프를 먹었나요?"},
            )

        classifier.assert_not_called()
        self.assertEqual(self.game_session.question_logs.count(), 1)

    def test_question_length_is_limited(self):
        with patch("game.views.classify_question") as classifier:
            self.client.post(
                reverse("game:ask_question", args=[self.game_session.id]),
                {"question_text": "가" * 501},
            )

        classifier.assert_not_called()
        self.assertEqual(self.game_session.question_logs.count(), 0)

    def test_openai_error_is_shown_without_creating_question_log(self):
        with patch("game.views.classify_question", side_effect=OpenAIServiceError("API 호출 실패")):
            response = self.client.post(
                reverse("game:ask_question", args=[self.game_session.id]),
                {"question_text": "남자는 수프를 먹었나요?"},
                follow=True,
            )

        self.assertContains(response, "API 호출 실패")
        self.assertEqual(self.game_session.question_logs.count(), 0)

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

        self.assertContains(response, "이어하기")
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


class OpenAIUsageLogTests(TestCase):
    def test_records_token_usage_without_prompt_content(self):
        usage = type("Usage", (), {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15})()
        response = type("Response", (), {"usage": usage})()

        _record_openai_usage("question_classification", response=response)

        log = OpenAIUsageLog.objects.get()
        self.assertEqual(log.input_tokens, 10)
        self.assertEqual(log.output_tokens, 5)
        self.assertEqual(log.total_tokens, 15)
        self.assertTrue(log.success)

    @override_settings(OPENAI_API_KEY="secret-test-key")
    def test_redacts_api_key_from_error_log(self):
        _record_openai_usage("question_classification", error_message="failed with secret-test-key")

        self.assertEqual(OpenAIUsageLog.objects.get().error_message, "failed with [redacted]")


class OpenAIIntegrationTests(TestCase):
    def test_openai_question_classifier_returns_expected_label(self):
        with patch("game.services._classify_question_locally", side_effect=AssertionError("OpenAI API was not called.")):
            response_label = classify_question(
                scenario="남자가 식당에서 바다거북스프를 먹고 집에 돌아가 자살했다.",
                answer_text="남자는 과거 조난 때 먹은 음식이 인육이었다는 사실을 식당의 수프 맛으로 깨달았다.",
                question_text="남자는 식당에서 수프를 먹었나요?",
            )

        self.assertEqual(response_label, "맞습니다")

    def test_openai_final_answer_classifier_returns_expected_label(self):
        response_label = classify_final_answer(
            scenario="남자가 식당에서 바다거북스프를 먹고 집에 돌아가 자살했다.",
            answer_text="과거 조난 때 인육 수프를 먹었고, 식당의 진짜 바다거북스프 맛으로 진실을 깨달았다.",
            answer_checkpoints=[
                "과거 조난 상황에서 수프를 먹었다.",
                "과거에 먹은 수프는 인육 수프였다.",
                "식당의 진짜 바다거북스프 맛으로 진실을 깨달았다.",
            ],
            submitted_answer=(
                "남자는 과거 조난 상황에서 수프를 먹었다. 과거에 먹은 수프는 인육 수프였다. "
                "식당의 진짜 바다거북스프 맛으로 진실을 깨달았다."
            ),
        )

        self.assertEqual(response_label, FINAL_ANSWER_CORRECT)

    def test_openai_generates_puzzle_criteria(self):
        criteria = generate_puzzle_criteria(
            scenario="남자가 식당에서 바다거북스프를 먹고 집에 돌아가 자살했다.",
            answer_text="과거 조난 때 인육 수프를 먹었고, 식당의 진짜 바다거북스프 맛으로 진실을 깨달았다.",
        )

        self.assertTrue(criteria["answer_checkpoints"])
        self.assertTrue(criteria["question_yes_facts"])
        self.assertTrue(criteria["question_no_facts"])
