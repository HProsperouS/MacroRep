# Follow-ups

Known gaps and deferred decisions, so they aren't lost between work sessions.
Remove an item once it's done.

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
