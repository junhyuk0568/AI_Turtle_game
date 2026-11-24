# Plan 003 - Live Claude verification (P1)

Status: Complete; user chose claude-sonnet-5-5 (test-claude PASS on Sonnet, 14.6 s)
Lane: Feature/fix (verification, usage logging fix)

## Outcome
- test-claude (3 billed integration tests) PASS on claude-opus-5-5:
  .harness/web/state/verification-b73bb21c-c8e6-4d7a-9943-0dab08b0586e.json
- 16-question judging eval (6 starter test cases + 10 probes: dark wording,
  trap, compound/partial, history follow-up, prompt injection, irrelevant),
  effort low, run on a preview DB copy on 2026-11-24.

| Model | Accuracy | Refusals | Avg latency | Cost / question | Cost / 1,000 questions |
|---|---|---|---|---|---|
| claude-opus-5-5 | 16/16 | 0 | 2.2 s | $0.00132 | $1.32 |
| claude-sonnet-5-5 | 16/16 | 0 | 1.3 s | $0.00057 | $0.57 |
| claude-haiku-5-5 | 14-15/16 | 0 | 2.2 s | $0.00009 | $0.09 |

- Prompt ~1,770 tokens per question, 96% served from the prompt cache when calls
  for the same puzzle arrive within the cache window. Costs use the skill price
  table cached 2026-11-03 (Haiku cache-read price assumed 10% of input).
- Haiku misses: history follow-up ("그때 먹은 수프가 문제였나요?") and one
  dark-wording question judged "일부만 맞습니다"/"질문이 모호합니다".
- No refusals for cannibalism/suicide wording on any model.

## Fixes found during verification
- AIUsageLog ignored cached prompt tokens (cache_read/cache_creation), so admin
  usage showed ~60 input tokens instead of ~1,770. Added both fields (migration
  0011); total_tokens now includes them.
- Starter puzzle got checkpoint hints (local DB + fixture); hint 1 avoids adding
  "바다", which the registered truth does not state.

## Limits of this evidence
- One puzzle, 16 questions, single run per model; small sample.
- Final-answer judging and criteria generation verified only by test-claude.
- GitHub Actions secret not yet confirmed by a CI run.
