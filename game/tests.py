from django.test import TestCase

from .models import Puzzle, QuestionTestCase
from .services import (
    FINAL_ANSWER_CORRECT,
    FINAL_ANSWER_INSUFFICIENT,
    _classify_final_answer_locally,
    _classify_question_locally,
    _normalize_label,
    classify_question,
    generate_puzzle_criteria,
)


class QuestionClassifierTests(TestCase):
    def test_normalize_label_strips_extra_text(self):
        self.assertEqual(_normalize_label("맞습니다."), "맞습니다")
        self.assertEqual(_normalize_label("결과: 관계없습니다"), "관계없습니다")
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
            classify_question(
                scenario="한 남자가 식당에서 수프를 먹고 집에 돌아온 뒤 자살했다.",
                answer_text="그는 식당의 수프를 통해 과거의 진실을 깨달았다.",
                question_text="남자는 원래 자살 계획이 있었나요?",
                question_criteria=criteria,
            ),
            "아닙니다",
        )
        self.assertEqual(
            classify_question(
                scenario="한 남자가 식당에서 수프를 먹고 집에 돌아온 뒤 자살했다.",
                answer_text="그는 식당의 수프를 통해 과거의 진실을 깨달았다.",
                question_text="남자는 식당에서 수프를 먹었나요?",
                question_criteria=criteria,
            ),
            "맞습니다",
        )

    def test_generate_puzzle_criteria_local_fallback(self):
        criteria = generate_puzzle_criteria(
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

        answer_label = classify_question(
            scenario=puzzle.scenario,
            answer_text=puzzle.answer_text,
            question_text=test_case.question_text,
            question_criteria=puzzle.get_question_criteria(),
        )
        test_case.mark_result(answer_label)

        self.assertEqual(test_case.last_answer_label, "맞습니다")
        self.assertTrue(test_case.last_passed)
        self.assertIsNotNone(test_case.last_run_at)
