# Follow-ups

Known gaps and deferred decisions, so they aren't lost between work sessions.
Remove an item once it's done.

## Decisions deferred

### Calorie target range: app form vs. server

The Profile page's targets form accepts **1,000–6,000 kcal** (protein ≤ 500 g,
fat ≤ 400 g). The server accepts **0–10,000 kcal** (macros ≤ 1,000 g). The form
is deliberately stricter for now.

Before widening the form to the server's range, make sure the coach can handle
a very low target. With a 0 kcal target, the placeholder pipeline
(`backend/app/coach/pipeline.py`) proposes a *negative* target, and the edit
form (`frontend/src/components/coach/edit-proposal-form.tsx`) can't correct it
because it only allows ±25% of the current value (±25% of 0 is 0).

- **Revisit with:** step 4, safe limits for plan changes. The coach must never
  propose a negative or implausibly low target, whatever the form allows.
- **Open question:** raise only the form's upper limit to 10,000 (so a large
  athlete can set 6,500) while keeping the 1,000 floor?

### Logging completeness (step 3)

Needs a definition of a *complete*, *partial*, and *missing* day. Suggested:
missing = nothing logged; partial = under 50% of the calorie target;
complete = otherwise.

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

- **Adding a weigh-in:** only possible from Home, and only while today has no
  weigh-in. Add an "Add weigh-in" button to the Progress page's Weigh-ins list
  and the Home trend-weight card, so missed days can always be filled in.
- **Adherence label:** the Progress page's Adherence stat says "Days within
  ±10% of target", but it measures days with *any* food logged. Fix the
  wording, or compute the real figure, as part of step 3.
- **Apply doesn't change the plan:** applying a coach proposal records the
  decision but doesn't update targets or the workout plan yet.

## Verification pending

- **Migration `e5a9d2c4f1b6`** (food-entry quantity) hasn't been run against
  Postgres yet. The dev container applies it on start (`docker compose up`).
- **Tests run on SQLite,** which ignores numeric column sizes. Input limits
  are set to fit every column, but running the suite against Postgres in CI
  would prove no oversized value can overflow one.
