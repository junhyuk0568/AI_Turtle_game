import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from game.management.puzzle_io import serialize_puzzles, starter_titles
from game.models import Puzzle


class Command(BaseCommand):
    help = "Export puzzles with answers and test questions to a private JSON file (never commit it)."

    def add_arguments(self, parser):
        parser.add_argument("output", help="Path of the JSON file to write, e.g. private/puzzles.json")
        parser.add_argument("--title", action="append", default=[], help="Only this title (repeatable).")
        parser.add_argument(
            "--exclude-starter", action="store_true", help="Skip puzzles that are already in the public fixture."
        )

    def handle(self, *args, output, title, exclude_starter, **options):
        puzzles = Puzzle.objects.order_by("id")
        if title:
            puzzles = puzzles.filter(title__in=title)
        if exclude_starter:
            puzzles = puzzles.exclude(title__in=starter_titles())
        puzzles = list(puzzles)
        if not puzzles:
            raise CommandError("No puzzles matched.")
        path = Path(output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(serialize_puzzles(puzzles), ensure_ascii=False, indent=2), encoding="utf-8")
        titles = ", ".join(puzzle.title for puzzle in puzzles)
        self.stdout.write(self.style.SUCCESS(f"Exported {len(puzzles)} puzzle(s) to {path}: {titles}"))
        self.stdout.write(self.style.WARNING("This file contains answers. Keep it out of Git."))
