"""Move puzzles between databases without putting their truths in Git.

Files written here contain full answers. Keep them in an ignored folder such as
private/ and copy them to the server by a private channel.
"""
import json
from pathlib import Path

from django.db import transaction

from game.models import Puzzle, QuestionTestCase

FORMAT_VERSION = 1
PUZZLE_FIELDS = (
    "scenario",
    "answer_text",
    "answer_checkpoints",
    "checkpoint_hints",
    "question_yes_facts",
    "question_no_facts",
    "question_irrelevant_facts",
    "question_ambiguous_examples",
    "hint1",
    "hint2",
    "hint3",
    "is_active",
)
STARTER_FIXTURE = Path(__file__).resolve().parent.parent / "fixtures" / "starter_puzzles.json"


def starter_titles():
    data = json.loads(STARTER_FIXTURE.read_text(encoding="utf-8"))
    return {item["fields"]["title"] for item in data if item["model"] == "game.puzzle"}


def serialize_puzzles(puzzles):
    return {
        "version": FORMAT_VERSION,
        "puzzles": [
            {
                "title": puzzle.title,
                **{field: getattr(puzzle, field) for field in PUZZLE_FIELDS},
                "test_cases": [
                    {"question_text": case.question_text, "expected_label": case.expected_label, "memo": case.memo}
                    for case in puzzle.question_test_cases.order_by("id")
                ],
            }
            for puzzle in puzzles
        ],
    }


@transaction.atomic
def import_payload(payload, dry_run=False):
    """Upsert puzzles by title and their test cases by question text. Returns counts."""
    if payload.get("version") != FORMAT_VERSION or not isinstance(payload.get("puzzles"), list):
        raise ValueError("Unsupported puzzle file format.")
    valid_labels = {label for label, _ in QuestionTestCase.LABEL_CHOICES}
    counts = {"created": 0, "updated": 0, "tests_created": 0, "tests_updated": 0}
    for item in payload["puzzles"]:
        title = (item.get("title") or "").strip()
        if not title:
            raise ValueError("Every puzzle needs a title.")
        values = {field: item[field] for field in PUZZLE_FIELDS if field in item}
        puzzle, created = Puzzle.objects.update_or_create(title=title, defaults=values)
        counts["created" if created else "updated"] += 1
        for case in item.get("test_cases", []):
            if case.get("expected_label") not in valid_labels:
                raise ValueError(f"Invalid expected_label in {title}: {case.get('expected_label')!r}")
            _, case_created = QuestionTestCase.objects.update_or_create(
                puzzle=puzzle,
                question_text=case["question_text"],
                defaults={"expected_label": case["expected_label"], "memo": case.get("memo", "")},
            )
            counts["tests_created" if case_created else "tests_updated"] += 1
    if dry_run:
        transaction.set_rollback(True)
    return counts
