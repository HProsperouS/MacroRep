# Follow-ups

Known gaps and deferred decisions, so they aren't lost between work sessions.
Remove an item once it's done.

## Next release

- **Drop the legacy refresh-token columns.** `users.refresh_token_hash` and
  `users.refresh_expires_at` are unused since `b4f0d6c2e8a5` (one session per device) but
  were kept so the previous release's tasks keep working during that deploy. In the
  release after it, remove them from `User` (`app/identity/models.py`) and add a migration
  that drops them. Not before: in the same release, `alembic upgrade head` would drop them
  while old tasks still read them, failing every signed-in request until they're replaced.

## Before production

The open items in [`deployment.md`](deployment.md#not-ready-for-production-yet), and why
each is still open:

- **A monthly budget on the OpenAI project.** Set in the OpenAI dashboard (Limits), not in
  code. The app bounds each user's AI calls, but only the provider's budget caps the total.
- **Sign-in limits for more than one task.** The attempt counts are in each task's memory.
  Decided to keep them there while it runs on one task; before scaling out, add an AWS WAF
  rate-based rule, or move them to Redis or Postgres (as `app/shared/usage.py` does for the
  AI limits).
- **No infrastructure code or deploy pipeline.** The AWS resources and the release steps in
  `deployment.md` are manual; CI builds the image but pushes nothing.

## Verification pending

- **Food catalogue values:** `app/food/catalog.py` was compiled to follow USDA
  FoodData Central and the Health Promotion Board's food composition data, but
  not checked line by line against them. Spot-check a sample, and confirm HPB's
  terms allow its figures in the project (USDA's are public domain).
