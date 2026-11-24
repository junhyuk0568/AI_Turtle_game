# Calendar Acceptance

Select only existing or requested behavior. This checklist does not authorize
new features. Mark PASS, FAIL, NOT RUN, or N/A with evidence/reason.

| Area | Observable check |
|---|---|
| Create | Valid input appears on intended date exactly once |
| Edit | Only the selected event changes; identity remains stable |
| Delete | Only selected event disappears; confirmation/undo matches specification |
| Persistence | Refresh/reopen retains expected data |
| Dates | Month/year boundaries and leap dates display correctly |
| All-day | Date-only events do not shift during timestamp conversion |
| Time | Start/end ordering and timezone follow the documented convention |
| Completion | Status persists without moving the event unexpectedly |
| Validation | Empty title and invalid time produce useful feedback |
| Empty state | Days without events remain understandable |
| Mobile | Selection, dialog, keyboard, scrolling, and saving remain usable |
| Errors | Load/save failure is visible; failed writes do not appear saved |
| Accounts, if present | Server enforces event ownership |
| Sync, if present | Multiple-device changes follow a defined conflict policy |
| Recurrence, if present | Single occurrence versus series edit is explicit |
| Backup, if present | Export/restore preserves dates and content |

Record browser, screen size, fixture data, actions, and observed results.
Use synthetic data; never test destructive cases on production calendars.
