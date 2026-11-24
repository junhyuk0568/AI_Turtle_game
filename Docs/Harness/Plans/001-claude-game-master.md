# Plan 001 - Claude game master

Status: Complete (live Claude verified in plan 003)
Lane: Contract/data (AI provider switch, schema migration 0010)

## Outcome and scope
- Observable user result: Claude judges questions as the game master with five
  internal labels shown as four short replies (그렇습니다 / 그렇지 않습니다 /
  그럴 수도 있습니다 / 관계없습니다), gives hints for still-unrevealed checkpoints, states in the answer
  dialog how many key keywords the answer must include, shows
  "핵심 N개 중 M개를 맞혔어요" on wrong final answers, and lets players report odd judgements.
- Files: game/services.py, views.py, admin.py, models.py, urls.py, tests.py,
  migrations/0010_claude_game_master.py, templates/game/play.html,
  config/settings.py, requirements.txt, .env examples, CI workflow, README, DEPLOYMENT.
- Will not touch: scoring rules, home/result pages, auth.

## Decisions
- Claude returns schema-constrained JSON only (output_config.format); templates
  build all player-facing text, so the hidden truth is never echoed.
- Final-answer verdict is decided in code: every checkpoint must be met.
- Default model claude-opus-5-5 at effort low; server-side refusal fallback
  ("default") on by default, switchable via GAME_CLAUDE_REFUSAL_FALLBACK.
- Env vars use a GAME_ prefix because Claude Code exports CLAUDE_EFFORT etc.
- OpenAIUsageLog renamed to AIUsageLog (RenameModel keeps old rows).
- Integration tests are tagged `claude_api`; offline suite excludes the tag.

## Recovery
- Migration 0010 applied to the tracked db.sqlite3 on 2026-11-24. Pre-migration
  copy kept outside the repo; `git checkout -- db.sqlite3` restores the committed DB.
- Reverting the code requires `migrate game 0009` first.

## Evidence
- 2026-11-24 offline gate: django-check, migrations-check, test-offline (41 tests)
  PASS - .harness/web/state/verification-9deb4817-591f-4c2d-8a75-a88fe6cd1804.json.
- 2026-11-24 user feedback: key-question badge removed (no `important` flag);
  replies shortened to four phrases. Truth-progress bar and matched-count feedback
  removed; answer dialog shows the required keyword count. Matched-count feedback
  on wrong answers restored at the user's request.
- Browser (preview DB copy with a seeded game): partial label,
  checkpoint hint skipping a revealed checkpoint,
  report -> "신고 접수됨", missing-key error message, mobile 375px layout - observed.
- NOT RUN: test-claude (no ANTHROPIC_API_KEY), real gameplay judging quality,
  refusal behaviour on dark puzzle themes, CI with the new secret.

## Next
1. User adds ANTHROPIC_API_KEY to .env and the GitHub secret.
2. Run test-claude and the admin "테스트 질문 실행" on the starter puzzle.
3. Generate checkpoint hints for existing puzzles (admin "AI 판정 기준 생성" or by hand).
