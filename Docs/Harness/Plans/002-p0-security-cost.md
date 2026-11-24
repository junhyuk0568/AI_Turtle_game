# Plan 002 - P0 security and cost

Status: Complete (admin password rotated by the user 2026-11-24; history cleanup optional)
Lane: Contract/data (access control, abuse limits, repository data)

## Outcome and scope
- Only the owner of a game (same anonymous session, or the logged-in user it
  belongs to) can view or act on it; everyone else gets 404.
- Billed Claude calls (questions, final answers) are limited per client IP per
  minute (GAME_AI_CALLS_PER_MINUTE, default 10) and questions per game
  (GAME_MAX_QUESTIONS_PER_GAME, default 100). Duplicates use no quota.
- db.sqlite3 is no longer tracked; starter puzzle + 6 question test cases live in
  game/fixtures/starter_puzzles.json (test results reset). Staged-path policy
  now blocks *.sqlite3.
- Will not touch: login/signup flows, admin permissions.

## Decisions
- Ownership: user-owned games require that user; otherwise the session key must
  match. Games with neither (legacy rows) are not served.
- Rate limit uses the default cache with REMOTE_ADDR; production needs a shared
  cache and real client IP forwarding (documented in README/DEPLOYMENT).

## Recovery
- Local db.sqlite3 is untouched on disk; `git rm --cached` only.
- The old DB (with a superuser password hash and play logs) remains in Git
  history of a PUBLIC repository. Rotating the admin password is required;
  rewriting history is optional and needs explicit user approval (force push).

## Evidence
- 2026-11-24 offline gate: 52 tests PASS (ownership, limits, fixture tests added).
- Browser: see ACTIVE_CONTEXT validation.
