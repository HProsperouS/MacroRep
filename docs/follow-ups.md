# Follow-ups

Known gaps and deferred decisions, so they aren't lost between work sessions.
Remove an item once it's done.

## Decisions deferred

### Calorie target range: app form vs. server

The Profile page's targets form accepts **1,000–6,000 kcal** (protein ≤ 500 g,
fat ≤ 400 g). The server accepts **0–10,000 kcal** (macros ≤ 1,000 g). The form
is deliberately stricter for now.

The coach can't push a target outside 1,000–6,000 kcal: its proposals are held
to those bounds (`backend/app/coach/agents/limits.py`), and applying one outside
them is refused (422). The proposal edit form still limits kcal edits to ±25% of
the current value, which would be stuck at a 0 kcal target, but the form never
lets a target go below 1,000.

- **Open question:** raise only the form's upper limit to 10,000 (so a large
  athlete can set 6,500) while keeping the 1,000 floor? The coach's 6,000 cap
  would then need raising too.

### Password rules

Passwords only need 8–128 characters, so `password`, `12345678`, the account's
own email, and 8 spaces are all accepted. Options discussed: reject
whitespace-only passwords and ones equal to the email, and check new passwords
against a common-password list (NIST SP 800-63B), either a small built-in list
(~200) or a bundled one (~10,000). Deliberately left as is for now.

## Known gaps

- **No login rate limiting:** unlimited wrong-password attempts are answered
  (30 in a row, then the right one, all worked), and registering a taken email
  says so, which lets addresses be checked in bulk. `plan.md` §17 asks for
  login rate limits. Proposed: ~5 failed attempts per email per 15 minutes
  plus a per-IP cap, returning 429. An in-memory limiter (`slowapi`) works
  locally; on AWS with several containers it needs a shared store (Redis) or
  an AWS WAF rate-based rule.

## Verification pending

- **Migrations don't run on SQLite:** `alembic upgrade head` against a SQLite
  database stops at `a1f4c9e2b7d3`, which drops a column without batch mode
  (`ALTER TABLE users DROP COLUMN cognito_subject`). The README's SQLite quick
  start works only with `AUTO_CREATE_SCHEMA=true`. CI checks the migrations on
  Postgres only.
- **Column sizes:** local test runs use SQLite, which ignores numeric column
  sizes; CI runs the suite on Postgres, where a test saving a value too big for
  its column fails. Input limits are set to fit every column, but not every
  limit has a test that saves its maximum value.
