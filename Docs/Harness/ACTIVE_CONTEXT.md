# Active Context

Status: Needs Verification
Active plan: Docs/Harness/Plans/001-claude-game-master.md

## Current work
Claude game-master upgrade implemented (steps 1-4): Claude API with structured
judging and question history, four short host replies (no key-question badge,
per user feedback), checkpoint-based hints, required keyword count in the answer dialog
and matched count on wrong answers (no progress bar, per user feedback), player judgement
reports that admins register as question test cases. Nothing committed.

## Decisions
- Default model claude-opus-5-5, effort low, refusal fallback on; all via GAME_* env vars.
- Claude returns JSON only; templates build player-facing text.
- Migration 0010 (RenameModel to AIUsageLog + new fields) applied to tracked db.sqlite3.
- Harness: Codex-only parts not wired; no pre-commit hook.

## Validation
- 2026-11-24 offline gate PASS (django-check, migrations-check, test-offline 41 tests):
  .harness/web/state/verification-9deb4817-591f-4c2d-8a75-a88fe6cd1804.json
- Browser on a preview DB copy: new play-screen features and missing-key error observed.
- test-claude: NOT RUN (no ANTHROPIC_API_KEY). Live judging quality and refusal
  behaviour unverified. CI needs the ANTHROPIC_API_KEY secret.

## Next action (backlog 2026-11-24)
P0 security/cost: DONE in plan 002 (ownership 404, per-IP and per-game limits,
   DB untracked + fixture). User must rotate the admin password (old hash is in
   public Git history).
P1 live verification (needs user's ANTHROPIC_API_KEY): test-claude, existing
   6 question test cases, refusal check on dark themes, generate checkpoint hints,
   push + GitHub secret.
P2 content/UX: more puzzles (only 1 active), result-page question replay,
   waiting UX for slower judging.
P3 deployment: static files, WSGI server, managed DB.
