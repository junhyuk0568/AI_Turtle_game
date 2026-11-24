# AI_Turtle_game Agent Instructions

Django 6 web game (lateral-thinking "turtle soup" puzzles) where the Claude API acts
as the game master and judges questions and final answers. See README.md for setup and DEPLOYMENT.md
for production steps. Converse with the user in Korean; keep repository docs in English.

## Web Harness Routing

Read Docs/Harness/SESSION_BOOTSTRAP.md at session start and resume. Use its
current-state authority (Docs/Harness/ACTIVE_CONTEXT.md) and exact active plan.
Preserve the existing stack (Python/Django, pip + requirements.txt), Git hooks,
GitHub Actions workflow, accepted behavior, and unrelated edits.

Follow Docs/Harness/WORKFLOW.md for work-size selection and the feedback loop.
Use brief scope/evidence for small edits, a short acceptance plan for features,
and explicit compatibility/recovery for data or access contracts. Resolve routine
reversible choices autonomously; ask only for consequential unknowns or missing
authority. Existing authorization remains valid within its scope.

Run checks relevant to the changed behavior:
`node .harness/web/verify.mjs --check NAME --run` supports iteration;
PARTIAL_PASS does not satisfy omitted checks. Check names and commands live in
.harness/web/config.json. `test-claude` makes real, billed Claude API calls:
run it only when the Claude request contract changed or before a release.
Complete the applicable integration gate and actual browser acceptance before
declaring the task complete. Unavailable required evidence remains Needs Verification.

At meaningful boundaries update one authoritative current-state record. Avoid
repeating the same change in every document; honor stronger target requirements.
Apply user feedback within the active scope and do not restart completed work.

Harness adoption does not itself authorize new application features, commit/push,
deployment, data mutation, or weaker safeguards. Use separately established
authorization without adding redundant approval steps.

## Project rules

- Never print, log, or commit `.env` values or the Anthropic API key.
- `db.sqlite3` is tracked because it holds the starter puzzles. Do not commit
  local play data or test edits to it; schema changes need a migration.
- Real gameplay judging always calls Claude; do not hide API failures behind
  local fallbacks (see README "진행자(Claude) 동작").
- Claude returns schema-constrained JSON only; player-facing text comes from
  templates so the hidden truth is never echoed. Keep it that way.
- Game env vars use the `GAME_` prefix; Claude Code sets its own `CLAUDE_*`
  variables (e.g. `CLAUDE_EFFORT`) that must not leak into game settings.
