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

- **Migrations don't run on SQLite:** `alembic upgrade head` against a SQLite
  database stops at `a1f4c9e2b7d3`, which drops a column without batch mode
  (`ALTER TABLE users DROP COLUMN cognito_subject`). The README's SQLite quick
  start works only with `AUTO_CREATE_SCHEMA=true`. CI checks the migrations on
  Postgres only.
- **Column sizes:** local test runs use SQLite, which ignores numeric column
  sizes; CI runs the suite on Postgres, where a test saving a value too big for
  its column fails. Input limits are set to fit every column, but not every
  limit has a test that saves its maximum value.
