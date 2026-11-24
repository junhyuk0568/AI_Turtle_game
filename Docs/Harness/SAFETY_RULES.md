# Web Development Safety Rules

Stack-neutral operating rules for the adopted web repository. These rules do not
assume a framework, database, hosting provider, product, or source-project defect.
Retain the target's established safety authority and merge compatible rules once.
User instructions and already-established authorization govern task scope.

## Repository and execution

- WEB-001: Preserving unrelated edits and existing Git history is required - reset, cleanup, or replacement can destroy user work.
- WEB-002: Preserving the existing package manager, lockfile, hook chain, and deployment identity during harness-only work is required - changing them alters the application outside the migration scope.
- WEB-003: Reviewing commands and their working directory before execution is required - scripts named build or test can still deploy, delete data, or target the wrong service.
- WEB-004: Passing user-derived values as literal arguments or through a verified parser is required - shell string interpolation can execute unintended commands.
- WEB-005: Testing destructive cases against disposable fixtures is required - production or personal data can be permanently lost.

## Secrets and data

- WEB-006: Placing credentials or private environment values in source, browser bundles, prompts, snapshots, or reports is forbidden - these surfaces can expose reusable access.
- WEB-007: Keeping actual secret values out of tracked environment examples is required - an allowed example filename does not make its contents safe.
- WEB-008: Identifying the exact environment and a recovery path before an authorized schema migration or bulk mutation is required - incompatible changes can corrupt or erase persisted data.
- WEB-009: Reporting failed saves as failures and retaining recoverable input is required when implementing persistence - displaying success without storage loses user data.

## Application boundaries (apply when the feature exists)

- WEB-010: Server-side authentication and resource ownership checks are required for private API operations - hiding controls in the browser does not prevent unauthorized requests.
- WEB-011: Validating untrusted input at the receiving boundary is required - browser-only validation can be bypassed.
- WEB-012: Using parameterized database operations and context-appropriate output encoding is required - concatenated queries or unsafe HTML can execute injected input.
- WEB-013: Preserving existing API and persisted-data contracts or providing an explicit migration is required - silent shape changes break callers and stored records.
- WEB-014: Documenting date-only versus timestamp and timezone semantics before changing date handling is required - implicit conversion can shift scheduled dates.

## Verification and release

- WEB-015: Validating the complete check configuration before any check command runs is required - a malformed later entry otherwise permits partial execution.
- WEB-016: Recording pass, fail, not-run, and genuinely not-applicable checks separately is required - missing evidence must not become a successful verification.
- WEB-017: Checking the actual user flow when changing UI or persistence is required for behavioral completion - a successful build does not demonstrate usable or durable behavior.
- WEB-018: Confirming target environment and existing authorization before push, deployment, access changes, or data mutations is required - local development permission alone does not authorize external effects.
- WEB-019: Preserving existing approvals and their scope is required - repeatedly asking for already-granted permission blocks authorized work.
- WEB-020: Restoring only an exact-session snapshot while keeping current documents authoritative is required - another session or stale history can redirect current work.

## Enforcement

These are operating instructions and review criteria. The bundled path guards
enforce only configured filenames, not all rules above. A secret-content scanner,
API authorization tests, browser tests, CI, and deployment controls must come from
the target project where applicable. Do not claim those integrations exist merely
because this document is present.

Add new project-specific constraints only with relevant source evidence, scope,
consequence, and a concrete verification method. Follow the target's approval
procedure for protected rules; do not import another project's historical rules.
