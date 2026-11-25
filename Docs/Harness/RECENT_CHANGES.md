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

## 2026-11-24 - Questions without page reload (C1)
Files: game/views.py, templates/game/play.html, templates/game/_question_exchange.html,
game/tests.py, README.md.
Purpose: chat-like question flow while Claude judges.
Verification: offline gate PASS (65 tests); browser: pending bubble, reply, count update,
duplicate error inline, no console errors (one billed Sonnet call).

## 2026-11-24 - Result replay, cleared marks, test-run confirm, icon (C2, C3)
Files: game/views.py, game/admin.py, game/templatetags/game_extras.py,
templates/game/{result,home,base,_question_exchange}.html,
templates/admin/game/puzzle/run_tests_confirm.html, static/game/img/favicon.svg,
game/tests.py, README.md.
Verification: offline gate PASS (73 tests); browser: result replay, home badge, icon.

## 2026-11-24 - Smaller images (E1)
Files: static/game/img/{admin-avatar,user-avatar,game-logo}.webp, templates/game/{base,play,_question_exchange}.html.
Purpose: avatars (42 px) and header logo were 3.4 MB of PNG; now 38 KB of WebP.

## 2026-11-24 - Private puzzle transfer (E2)
Files: game/management/{puzzle_io.py,commands/export_puzzles.py,commands/import_puzzles.py},
game/tests.py, .gitignore, .harness/web/config.json, README.md, DEPLOYMENT.md.
Purpose: move puzzles with answers to a server without committing them.
Verification: offline gate PASS (79 tests); fresh scratch DB: migrate + loaddata + import -> 6 puzzles.

## 2026-11-25 - Google login and nicknames (plan 004 phase 1)
Files: config/settings.py, config/urls.py, requirements.txt (django-allauth 65.22.1),
game/{accounts,account_views,forms,middleware,context_processors,apps,models,admin,views,urls,tests}.py,
migration 0012, templates/game/{base,nickname,account_delete,privacy}.html, env examples, README, DEPLOYMENT.
Verification: offline gate PASS (92 tests); browser on a DB copy: guest header/footer, privacy page,
nickname redirect with next, nickname save, header nickname without email, logout.
Live check (user's local OAuth client, localhost:8000): guest game started, Google sign-in,
account created with no usable password and no stored tokens, nickname saved, guest game
moved to the account; no server errors. The first attempt fell back to allauth's signup form
because the admin account had the same email: admin email cleared (admin stays separate
from the player account), all allauth pages now use the site layout
(templates/allauth/layouts/base.html) and the email-conflict fallback explains instead of
asking for a username (templates/socialaccount/signup.html). Offline gate PASS (94 tests).
Google sign-in now shows the app name "AI 바다거북스프" (user renamed it in Branding).

## 2026-11-25 - Per-player daily caps and daily AI budget (plan 004 phase 2)
Files: game/limits.py (new), game/{models,views,admin,tests}.py, migration 0013
(DailyUsage, AIUsageLog.created_at index, createcachetable), config/settings.py
(database cache, GAME_DAILY_AI_CALLS_PER_ACCOUNT/_PER_GUEST, GAME_DAILY_AI_BUDGET_USD,
GAME_AI_PRICE_*_PER_MTOK), env examples, README, DEPLOYMENT.
Purpose: cap billed calls per account (300/day) and per guest session (50/day), stop player
calls when today's estimated spend reaches the budget ($5), and keep the per-minute window
in a database cache shared by workers. Admin AI usage list shows today's estimate.
Verification: offline gate PASS (100 tests); local DB migrated (backup kept in the session
scratchpad); browser on a DB copy with a simulated $100 day: question refused inline with the
budget message, typed question kept, no Claude call or usage row.
Gap: guests can reset their cap by clearing cookies (the budget is the backstop).

## 2026-11-25 - Rankings (plan 004 phase 3)
Files: game/rankings.py, game/ranking_views.py (new), game/{models,views,urls,accounts,admin,tests}.py,
game/templatetags/game_extras.py (play_time), migration 0014 (final_score, play_seconds,
is_ranked + partial unique constraint, backfill), templates/game/{ranking,_ranking_row}.html (new),
templates/game/{base,home,result}.html, README.
Purpose: first clear per account and puzzle is ranked (guest clears count after login claim);
overall and per-puzzle boards with nicknames only; result page shows rank, practice or login prompt;
home best score uses the stored clear score.
Verification: offline gate PASS (109 tests); local DB migrated (backfill ranked 1 existing clear;
backup kept in the session scratchpad); browser on a DB copy with three sample players and a
throwaway login: overall and puzzle boards, "(나)" highlight, result "3위" and practice note,
home ranking links, mobile layout (date column hidden); no server errors.
Gap: boards are computed in Python per request (fine at current scale; paginate or cache if
players grow into the thousands).

## 2026-11-25 - Case-file visual redesign (user request: less "AI-looking", eerie mood)
Files: templates/game/{base,home,play,_question_exchange,result,ranking,nickname,account_delete,privacy}.html,
templates/socialaccount/signup.html, templates/allauth/layouts/base.html (title), static/game/img/favicon.svg,
game/tests.py, README.
Purpose: the user picked direction A ("사건 기록부") from three mockups. Dark desk with a lamp vignette,
aged-paper cards with grain, Nanum Myeongjo / Gowun Batang (Google Fonts), red-ink stamps for solved
puzzles and host judgements; text wordmark replaces the mascot logo and avatars; copy reworded
(사건, 단서, 심문 기록, 진상 밝히기). Motion respects prefers-reduced-motion. Privacy page notes
that Google Fonts receives the visitor IP.
Verification: offline gate PASS (109 tests); browser on the DB copy at 1280px and 375px: home, play
with all four judgement stamps, final-answer dialog, result, ranking, nickname; no server errors.
Follow-up (user feedback): desk background lightened (#251e17), lighter vignette, and text
directly on the desk set bold with a brighter muted colour; text on paper unchanged.
Follow-up: "사건철" renamed to "사건 기록부" (wordmark, page titles, home label); Korean text
wraps between words (word-break: keep-all) so mobile lines no longer split words.
Gap: the old mascot images in static/game/img are no longer referenced (kept; delete if unwanted).

## 2026-11-25 - Host speaks in short plain sentences
Files: game/templatetags/game_extras.py (host_reply values, new host_verdict filter),
templates/game/play.html, game/tests.py, README.
Purpose: the play page intro promises short answers, so judgements read 그렇다 / 아니다 / 그럴 수도 /
관계없다 and the final-answer feedback reads "정답이다." / "아직 부족하다." / "핵심 N개 중 M개를 맞혔다."
Internal labels and the Claude contract are unchanged; system notices keep the polite style.
Verification: offline gate PASS; browser shows all four stamps in the new wording.
Follow-up: the unfamiliar word "미결" was replaced (header seal "사건", home label "미제 사건 기록부").
