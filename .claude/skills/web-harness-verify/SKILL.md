---
name: web-harness-verify
description: Verify a scoped web change using an adopted web harness, existing project checks, and browser acceptance evidence. Use for phase completion or explicit verification in a repository containing .harness/web/config.json.
---

# Scoped Web Verification

Read effective instructions, the active task, and the routing from
Docs/Harness/SESSION_BOOTSTRAP.md. Use WORKFLOW.md to scale effort to the change.

1. Map actual changed behavior and shared contracts to existing configured checks.
   Preserve baseline failures separately from new regressions.
2. Review commands/cwd. For iteration use verify.mjs --check NAME --run (repeat
   --check for multiple names); run without --run for read-only preflight.
   Selection does not bypass whole-config structural validation.
3. Treat PARTIAL_PASS as evidence for selected checks only. Review NOT_SELECTED
   and configurationStatus entries. Complete required integration/full checks
   before declaring the task's acceptance satisfied.
4. For changed UI/persistence, observe the applicable browser flow when available.
   CLI success, static doctor output, and user preference feedback are distinct
   from behavioral validation.
5. Reuse the generated result path in a concise task record; do not copy raw logs
   or secrets into context. Update one authoritative state at the work boundary.
6. Report unavailable verification explicitly and continue independent work.
   Do not add services, access changes, deployments or unrelated fixes without
   authority. Reuse existing permission instead of asking again.

Calendar changes may use relevant CALENDAR_ACCEPTANCE.md cases; that checklist
does not authorize new features. Do not infer security/accessibility or production
readiness from build success.
