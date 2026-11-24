@AGENTS.md

## Claude Code notes

- Project hooks in .claude/settings.json inject Docs/Harness/ACTIVE_CONTEXT.md at
  session start and save a same-session snapshot before compaction
  (.harness/web/session.mjs). Current documents always override snapshots.
- The kit's apply_patch guard is Codex-only and is not wired for Claude Code;
  the staged-path policy is `node .harness/web/policy.mjs`.
- The `web-harness-verify` skill (.claude/skills/) covers scoped verification.
