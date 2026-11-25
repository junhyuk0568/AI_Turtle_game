# Plan 004 - Rankings with Google login (multiplayer type A)

Status: Phases 1-2 DONE 2026-11-25 (phase 1 committed 067ab12; phase 2 not committed); phases 3-4 not started
Lane: Contract/data (accounts, personal data, new models, ranking rules)

## Decisions (user, 2026-11-25)
- Multiplayer = A: everyone plays alone; scores are compared on rankings.
- Ranked record = the FIRST clear of each puzzle per account. Later clears are
  practice (the truth is shown after a clear, so replays would score full marks).
- Only logged-in (Google) accounts appear on rankings. Guests can still play.
- Rankings show a self-chosen nickname, never the Google name or email.
- Scope: per-puzzle ranking + overall ranking (sum of first-clear scores).

## Phases and acceptance
### Phase 1 - Google login and nicknames
- django-allauth with the Google provider; keys via env (GOOGLE_CLIENT_ID,
  GOOGLE_CLIENT_SECRET). User creates the OAuth client in Google Cloud Console.
- On login, games owned by the previous guest session move to the account
  (session key changes at login).
- PlayerProfile(user 1:1, nickname unique, 2-12 chars, letters/digits/Korean/_ only).
  First login redirects to nickname setup; nickname can be changed later.
- Logout, privacy policy page (collected: email from Google, nickname, play
  records; purpose; retention; deletion), account deletion that removes profile,
  games and logs.
- Accept: login/logout locally; guest game survives login; nickname rules
  enforced; Google name/email never rendered on public pages.

### Phase 2 - Cost limits per player
- Daily cap on billed calls (questions + final answers) per account and per guest
  session (GAME_DAILY_AI_CALLS_PER_ACCOUNT / _PER_GUEST, DailyUsage model), in addition
  to the per-IP minute window; logged-in users limited by account.
- Service-wide daily Claude budget from AIUsageLog token costs
  (GAME_DAILY_AI_BUDGET_USD); over budget -> friendly "오늘은 마감" message.
- Rate-limit cache switched to a shared cache (database cache) so limits hold
  across workers.
- Accept: caps tested per account/guest; budget stop tested with fake usage rows.

### Phase 3 - Rankings
- GameSession.is_ranked set at clear time when it is the account's first clear
  of that puzzle (guest clears count after they move to the account).
- Order: score desc, then clear duration (cleared_at - created_at) asc, then
  cleared_at asc.
- Pages: overall ranking, per-puzzle ranking; result page says "이번 기록 N위" or
  "연습 기록 (순위 미반영)"; guests see "로그인하면 순위에 오를 수 있어요".
- Accept: replay never changes rank; guest-then-login first clear counts;
  ties ordered as above; only nicknames shown.

### Phase 4 - Deploy (Railway) and production OAuth
- gunicorn, whitenoise, volume for SQLite (or Postgres), DEBUG off, HTTPS,
  real client IP, production OAuth redirect URI, import_puzzles, check --deploy.

## Risks and non-goals
- Multiple Google accounts per person can still farm first clears; accepted.
- Personal data appears (Google email); keep it out of logs and public pages.
- New dependency (django-allauth and its requirements) is added to requirements.txt.
- Not in scope: shared rooms, real-time play, WebSockets (types B/C).

## Recovery
- Each phase lands as its own commit with migrations; rollback = revert the
  commit and migrate back to the previous migration.
