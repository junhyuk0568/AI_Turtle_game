# Iterative Web Development Workflow

## Start with the result
Turn the user's request into a short observable outcome. Inspect the relevant
existing screen/code and reuse its components and conventions. Resolve ordinary
reversible choices yourself. Ask only when an unknown changes product behavior,
data ownership, irreversible effects, or authorized scope; keep independent work
moving. Do not ask again for permission already established in the session.

## Choose effort by impact

| Lane | Trigger | Plan and record | Verification |
|---|---|---|---|
| Small edit | Copy, local spacing/color, isolated display adjustment | Brief scope plus a single result note; no new numbered plan | Relevant configured checks and inspect affected UI |
| Feature/fix | New behavior, bug fix, multi-file interaction | Short plan with observable acceptance and explicit non-goals | Relevant tests, actual user flow, then applicable integration checks |
| Contract/data change | Auth/ownership, API contract, schema, persisted data, deployment | Explicit compatibility/recovery and established authority before effects | Failure/ownership/migration cases and required release checks |

Lane selection is an agent judgment, not a classifier built into the tools.
A small-looking change to shared CSS or date logic can require broader checks.
Do not weaken an existing target rule to use a lighter lane.

## Iterate visibly
1. State the intended change and the few acceptance outcomes.
2. Build the smallest complete user-visible slice inside the authorized scope.
3. Show a local preview or report an observed interaction when available.
4. Apply user feedback to that same slice. Preserve accepted behavior and styling.
5. Run the relevant checks and record evidence. Repeat only after new changes,
   failures, or unresolved concerns justify it.

Treat mid-task corrections as steering, not a new project. Do not redesign nearby
screens, add dependencies, or change data architecture without a scoped reason.
A local preview is not a hosted deployment.

## Focused checks and final checks
Use verify.mjs --check NAME --run for a configured focused command; repeat
--check for multiple names. Names are exact config keys, not inferred from files.
Structural validation still checks the entire config before execution.
Unselected gaps remain visible and the result is PARTIAL_PASS, not full acceptance.
Use the default verify.mjs --run when the scoped completion/release gate requires
all configured commands. Fix malformed config instead of excluding its entry.

The harness does not determine test relevance automatically. Choose checks from
changed behavior, affected shared contracts, and the target's established policy.
Before finishing a feature, satisfy its acceptance checklist; do not stop after
a preview or partial pass while required checks remain.

## Evidence and baseline failures
Separate new failures from pre-existing failures. Fix regressions caused by the
authorized work. Record unrelated failures and continue independent checks.
After three consecutive failures of the same action, change method rather than
retrying indefinitely. Missing browser/tool evidence remains NOT RUN.

The verification runner records command results, not visual usability or security.
Do not invent browser results. If blocked from required acceptance, mark the task
Needs Verification rather than Complete and state exactly what remains.

## Minimal durable records
Keep one current-state authority. Update it once at a meaningful phase boundary,
pause, or handoff: outcome, decisions, changed files, checks/evidence, next action.
For a small edit, one concise recent-change record is enough; do not duplicate it
across every history document. Update the high-level changelog for significant
outcomes only. Honor stronger existing target requirements.

Resume by reading current state and its exact active plan, then inspect the current
diff. Do not rerun completed exploration unless files, constraints, or evidence
changed. Do not mark snapshots or configuration presence as live activation.

## Completion message
Report the user-visible result, evidence, and any material remaining gap.
Name the next required action only if work remains. Commit/push/deploy only within
established authorization; do not invent extra approval checkpoints for local work.
