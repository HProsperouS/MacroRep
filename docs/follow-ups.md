# Follow-ups

Known gaps and deferred decisions, so they aren't lost between work sessions.
Remove an item once it's done.

## Decisions deferred

### Password rules

Passwords only need 8–128 characters, so `password`, `12345678`, the account's
own email, and 8 spaces are all accepted. Options discussed: reject
whitespace-only passwords and ones equal to the email, and check new passwords
against a common-password list (NIST SP 800-63B), either a small built-in list
(~200) or a bundled one (~10,000). Deliberately left as is for now.

## Verification pending

- **Food catalogue values:** `app/food/catalog.py` was compiled to follow USDA
  FoodData Central and the Health Promotion Board's food composition data, but
  not checked line by line against them. Spot-check a sample, and confirm HPB's
  terms allow its figures in the project (USDA's are public domain).

- **Column sizes:** the tests run on Postgres, where saving a value too big for
  its column fails. Input limits are set to fit every column, but not every
  limit has a test that saves its maximum value.
