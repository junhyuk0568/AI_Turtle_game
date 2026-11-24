# Recent Changes

No application changes recorded.
At phase completion add date/task, files, purpose, verification, and remaining gaps.
Use or link the existing authoritative history rather than duplicating it.

## 2026-11-24 - Claude game master (plan 001)
Files: game/{services,views,admin,models,urls,tests}.py, migration 0010,
templates/game/play.html, config/settings.py, requirements.txt, env examples,
CI workflow, README, DEPLOYMENT, AGENTS.md, harness config.
Purpose: switch judging to Claude and add game-master presentation, adaptive
hints and judgement reports. Verification: offline gate PASS; browser observed;
test-claude not run. Gap: live Claude judging unverified.

## 2026-11-24 - P0 security and cost (plan 002)
Files: game/views.py, game/tests.py, game/fixtures/starter_puzzles.json,
config/settings.py, env examples, .gitignore, harness config, README, DEPLOYMENT, AGENTS.md.
Purpose: owner-only game access, billed-call limits, stop tracking db.sqlite3.
Verification: offline gate PASS (52 tests). Gap: admin password rotation (user).

## 2026-11-24 - Live Claude verification (plan 003)
Files: game/models.py, migration 0011, game/services.py, game/admin.py, game/tests.py,
game/fixtures/starter_puzzles.json, harness docs.
Purpose: verify real judging, compare models, log cached prompt tokens.
Verification: test-claude PASS; eval Opus 16/16, Sonnet 16/16, Haiku 14-15/16; offline gate below.

## 2026-11-24 - Starter title and criteria overwrite protection (B1, B3)
Files: game/admin.py, templates/admin/game/puzzle/generate_criteria_confirm.html,
game/fixtures/starter_puzzles.json, game/tests.py, README.md.
Purpose: real starter title; never overwrite hand-edited criteria without consent.
Verification: offline gate PASS (59 tests); admin confirm page and no-op path observed in browser.
