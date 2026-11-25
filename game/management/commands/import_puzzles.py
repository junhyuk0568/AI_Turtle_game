import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from game.management.puzzle_io import import_payload


class Command(BaseCommand):
    help = "Import puzzles from a private JSON file made by export_puzzles (upsert by title)."

    def add_arguments(self, parser):
        parser.add_argument("input", help="Path of the JSON file to read")
        parser.add_argument("--dry-run", action="store_true", help="Show what would change without saving.")

    def handle(self, *args, input, dry_run, **options):
        path = Path(input)
        if not path.is_file():
            raise CommandError(f"File not found: {path}")
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            counts = import_payload(payload, dry_run=dry_run)
        except (ValueError, KeyError) as exc:
            raise CommandError(str(exc)) from exc
        prefix = "Dry run - nothing saved. Would import" if dry_run else "Imported"
        self.stdout.write(
            self.style.SUCCESS(
                f"{prefix}: {counts['created']} new and {counts['updated']} updated puzzle(s), "
                f"{counts['tests_created']} new and {counts['tests_updated']} updated test question(s)."
            )
        )
