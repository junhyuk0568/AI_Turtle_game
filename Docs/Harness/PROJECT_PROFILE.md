# Project Profile

Status: CONFIGURED 2026-11-24 from repository evidence (commit f7b36c7).

| Field | Value / evidence |
|---|---|
| Project / Git root / app workspace | AI_Turtle_game; Git root = app root (single Django project) |
| Existing current-state authority | None before adoption; Docs/Harness/ACTIVE_CONTEXT.md is authoritative |
| Framework / language / runtime | Django 6.0.3, Python 3.13 (README, CI); apps: `config/` settings, `game/` app |
| Package manager / lockfile | pip + requirements.txt (Django, anthropic, python-dotenv); no lockfile |
| Development command / local URL | `python manage.py runserver` -> http://127.0.0.1:8000/ |
| Lint / typecheck / test / build | Lint, typecheck, build: N/A (none configured). Tests: `manage.py test` (Django TestCase) |
| Browser tools / critical routes | Home (puzzle list), play page, result page, Django admin |
| Existing CI / hooks / instructions | .github/workflows/tests.yml runs full `manage.py test` on push/PR with ANTHROPIC_API_KEY secret; no Git hooks; AGENTS.md/CLAUDE.md added by adoption |
| Storage / auth / timezone | SQLite `db.sqlite3` (local only, untracked since 2026-11-24; starter data in game/fixtures/starter_puzzles.json); Django sessions + auth; TIME_ZONE Asia/Seoul, LANGUAGE ko-kr |
| Deployment / access policy | Not deployed from this repo; DEPLOYMENT.md is a checklist only |
| Baseline failures | None. 2026-11-24: django-check, migrations-check, test-offline (18 tests) PASS on Python 3.13.13 .venv before the Claude migration; billed API test not run (no `.env`) |

## Authorized actions
Established 2026-11-24: local harness adoption edits on `main`; local `.venv` creation and requirements install.
Not established: application feature changes, dependency changes, commits,
pushes, deployments, data changes, Claude-billed test runs. Never record credential values.

## Everyday development defaults
- UI: Django templates in templates/game/ extending base.html; static images in static/game/img/.
- Local preview: `.venv/Scripts/python.exe manage.py runserver` (needs `.env` with ANTHROPIC_API_KEY for gameplay).
- Iteration checks: `django-check`, `migrations-check`, `test-offline`.
- Completion/release checks: all of the above plus `test-claude` (real, billed API calls) and CI.
- Browser availability: built-in browser pane can open the local server.

## Product scope
Existing behavior: puzzle list, play session with question judging (five labels incl.
partial, important flag, revealed checkpoints via Claude structured outputs), hints, final-answer judging, scoring (1000 start, -20 per question,
-150 per hint), resume of in-progress games, admin puzzle criteria generation and
AI usage logs, adaptive checkpoint hints, truth-progress bar, judgement reports
that admins turn into question test cases. Claude game-master upgrade (plan 001) implemented 2026-11-24.
CALENDAR_ACCEPTANCE.md does not apply to this project.

## Verification
Checks are mapped in .harness/web/config.json:
- `django-check`: `manage.py check`
- `migrations-check`: `manage.py makemigrations --check --dry-run`
- `test-offline`: `manage.py test game --exclude-tag=claude_api` (no network)
- `test-claude`: `manage.py test game --tag=claude_api` (requires ANTHROPIC_API_KEY, network, billed)
- `lint`, `typecheck`, `build`: N/A with reasons.
All Python checks use `.venv/Scripts/python.exe` (Windows). CI remains the
Linux full-test gate.
