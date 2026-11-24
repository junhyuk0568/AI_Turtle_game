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
- Default model claude-sonnet-5-5 (user choice after plan 003 eval), effort low, refusal fallback on; all via GAME_* env vars.
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
   DB untracked + fixture). Admin password rotated by the user 2026-11-24 (old
   hash remains in public Git history but no longer matches).
P1 live verification: DONE in plan 003 (test-claude PASS, 16-question model eval,
   no refusals, cache-token logging fixed, starter checkpoint hints). Model: Sonnet 5.5
   chosen by the user; test-claude PASS on it. CI secret run unconfirmed.
NEXT TO-DO (written 2026-11-24, not started):
A. Wrap-up of P1
  A1. Commit + push plan 003 work and the Sonnet 5.5 switch.
  A2. Confirm GitHub Actions passes with the ANTHROPIC_API_KEY secret (user registers it).
B. Content (P2)
  B1. Rename the starter puzzle ("첫 번째 테스트 문제" -> a real title) in DB + fixture.
  B2. Add 3-5 new puzzles: draft scenario/truth with the user, run "AI 판정 기준 생성",
      add 8-10 test questions each, run tests, activate.
  B3. Admin safety: "AI 판정 기준 생성" overwrites hand-edited criteria; confirm or
      fill only empty fields.
C. Player experience (P2)
  C1. Ask questions without a full page reload (fetch + pending bubble) so the
      1-2 s judging wait feels like a chat.
  C2. Result page: replay of the player's questions and the host's replies.
  C3. Home: mark cleared puzzles; optional "give up and see the answer" in play.
D. Deployment (P3)
  D1. Pick hosting; add WSGI server, static files, managed DB, shared cache,
      real client IP forwarding; run check --deploy.
  D2. Optional: GitHub Actions via Workload Identity Federation instead of a stored key.
