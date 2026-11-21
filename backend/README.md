# MacroRep backend

FastAPI modular monolith serving the endpoints the frontend already calls (see
`frontend/src/api/*.ts`): profile, food log, workouts, bodyweight, progress,
and the coach check-in flow.

## Structure

```text
backend/
├── app/
│   ├── main.py            # FastAPI entry point and middleware
│   ├── demo_seed.py        # idempotent local demo seed and its optional history
│   ├── core/                # typed configuration and DB session
│   ├── shared/               # logging, correlation IDs, persistence base, camelCase schema base, domain errors, rate limits, mail
│   ├── identity/              # current-actor resolution (self-issued JWT or local preview header)
│   ├── auth/                   # registration, login, refresh-token rotation, logout, email/password changes and resets
│   ├── profile/                 # fitness profile and nutrition targets
│   ├── food/                     # food catalog, daily food log, meal-photo estimates
│   ├── workout/                    # built-in/custom exercise catalog, weekly plan, logged sessions
│   ├── body/                        # weigh-ins and trend-weight calculation
│   ├── progress/                     # read-model composing the above into dashboard charts
│   ├── analytics/                     # deterministic nutrition, training and weight formulas
│   ├── coach/                          # check-ins, proposals, chat; agents/ is the LangGraph flow
│   └── health/                          # liveness/readiness/version
├── migrations/             # Alembic schema migrations
├── tests/                  # API, validation and formula tests (on PostgreSQL); helpers.py and fakes.py are shared
├── pyproject.toml
└── Dockerfile
```

Each domain normally owns `models.py`, `schemas.py`, `repository.py`,
`service.py`, and `router.py`. Services don't import FastAPI: they refuse a request
with a domain error from `app/shared/exceptions.py` (`NotFound`, `Conflict`,
`Invalid`, ...), which `app/shared/errors.py` turns into its HTTP status. The coach
module is split further by job (snapshot, apply, runner, factory); see
[`docs/architecture.md`](../docs/architecture.md#modules).

Tests share their setup instead of copying it: `tests/helpers.py` registers users and
logs food, weigh-ins and workouts through the API, and `tests/fakes.py` is a scripted
coach model for the agent, chat, revision and photo tests.

`app/workout/catalog.py` and `app/food/catalog.py` are the validated, append-only
sources for the built-in exercise and food libraries. Their Alembic data migrations
install the same global rows in every environment (`owner_id` is null);
`AUTO_CREATE_SCHEMA` installs them independently of demo data. A user's custom
exercises and foods use that user's id and are visible only to them. The foods'
values follow USDA FoodData Central (basic foods) and Singapore's Health Promotion
Board (hawker dishes and drinks), each row marked with its source. Every future catalog addition must include a new
additive data migration so already-upgraded databases receive it.

### Input validation

Every request body and query parameter is validated against an **allow-list**
before it reaches a service:

- Unknown fields are rejected (`extra="forbid"` on the shared `CamelModel`),
  as are `NaN` and `Infinity` in any number.
- Fixed-choice fields (meal, units, equipment, muscles, goal, …) accept only
  their listed values.
- Every number has a plausible range and every text field is trimmed and
  length-bounded, with no control characters or text-direction overrides
  (chat keeps line breaks; emoji and any script are fine). Ids in request
  bodies must look like ids (`[A-Za-z0-9_-]{1,64}`), and a NUL byte anywhere
  in the URL is refused with a 400 (`app/shared/request_guard.py`): Postgres
  can't store one, so it would otherwise surface as a 500. The ranges live in one place, `app/shared/validation.py`,
  and each fits its database column, so an oversized value is a 422, never a
  Postgres overflow. The frontend's forms mirror them.
- Cross-field rules: a workout can't finish before it starts or in the
  future, and calories can't be under half of what the macros imply (the
  reverse is allowed: alcohol has calories but no macros).

Validation errors return `{"message", "detail"}` without echoing the rejected
input back (see `app/shared/errors.py`). `tests/test_input_validation.py`
checks each limit from both sides.

### Known simplifications vs. a production system

- **The check-in agents use OpenAI or a rule-based stand-in.** The LangGraph
  flow in `app/coach/agents/` (Nutrition and Workout agents, a Reviewer, then
  deterministic validation) runs on OpenAI with `COACH_MODEL_PROVIDER=openai`
  and `OPENAI_API_KEY` set in `.env`, or on `FakeCoachModel` (the default),
  which answers each agent with simple rules and needs no key. Tests always use
  the fake. Coach Chat answers questions about a check-in from its data, and
  turns a requested change into a revised proposal for the user to apply.
- **No shared-record audit trail.** Unlike a multi-staff CRM, MacroRep
  records are single-owner personal data, so there's no admin/agent role
  hierarchy or soft-delete-with-named-actor trail — just plain
  `created_utc`/`updated_utc` timestamps and owner-scoped queries.
- **Auth is self-issued, not a third-party provider.** `app/auth` implements
  email/password registration and login (Argon2 hashing), a short-lived JWT
  access token, and a rotating refresh token stored as an httpOnly cookie —
  see that module's docstrings. Each signed-in device is a session of its own, and a user
  has one at a time (`MAX_SESSIONS_PER_USER`): signing in elsewhere drops the previous
  one. Access tokens carry their session's id and every request checks it still exists, so
  a device that's signed out loses access at once. New passwords need 8–128 characters and can't be
  only spaces, the account's email, or one of ~160 common passwords
  (`app/auth/passwords.py`). Changing the sign-in email and resetting a forgotten
  password are confirmed with a 6-digit code emailed to the address (15 minutes, 5
  tries, stored only as an HMAC); changing the password asks for the current one.
  Changing the password signs out every other device; resetting it signs out all of
  them, then signs in the one that reset it. Email goes out over SMTP when `SMTP_HOST` is set and is
  written to the log otherwise (`app/shared/mail.py`); production requires SMTP. Sign-in and sign-up attempts are limited
  (`app/shared/rate_limit.py`): in 15 minutes, 5 wrong passwords for an account
  from one address (so someone else guessing can't lock its owner out) and 30
  sign-ins per address; 50 wrong passwords for an account from anywhere and 10
  sign-ups per address an hour. Creates a client may retry after a lost answer (starting a
  check-in, finishing a workout, adding a food entry) take an `Idempotency-Key` header and
  answer a repeat with what the first one created (`app/shared/idempotency.py`). Emails go
  out after the response, so a slow mail server can't time a request out. An unhandled error
  answers 500 as JSON with the `correlationId` of its log line. Account changes: 5 wrong current passwords per user in
  15 minutes, 5 email-change codes per user an hour, 5 reset codes per email and 10 per
  address an hour, and 30 reset-code tries per address in 15 minutes. A reset request
  answers the same whether or not the email has an account. Coach Chat allows 30 messages and meal photos
  20 per user an hour, and check-ins 5 a day, since each is a paid model call; one
  that fails on our side is given back. Then 429 with `Retry-After`. `PREVIEW_AUTH_ENABLED` (on by default outside
  `APP_ENV=prod`) is a separate, additional local-dev seam: sending
  `X-Preview-Actor-Id: USR-DEMO` authenticates as the seeded demo user without
  going through login at all, useful for curling endpoints directly.

## Run locally

Install [uv](https://docs.astral.sh/uv/) and Python 3.12, then from `backend/`:

```bash
cp .env.example .env
uv sync

# Start PostgreSQL (docker) or point DATABASE_URL at your own instance, then:
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --port 8000
```

Or set `AUTO_CREATE_SCHEMA=true` in `.env` to skip Alembic locally (creates
tables directly from the models on startup — never use this in production).

Logs go to the console and, with `LOG_DIR=logs` (as in `.env.example`), also to daily
JSON-lines files in `backend/logs/`: `app-<date>.log` with everything and `error-<date>.log`
with errors only, including tracebacks and each request's correlation id. Files are kept
for 14 days. For example:

```bash
jq -r '[.timestamp, .event, .correlation_id] | @tsv' logs/error-$(date -u +%F).log
```

```bash
uv run ruff check app migrations tests evals
uv run mypy --config-file pyproject.toml app evals
uv run pytest
uv run pytest -n auto          # in parallel, one process per CPU core
uv run pytest --cov            # with branch coverage; fails below 90%
```

Tests run on PostgreSQL, the database the app runs on: by default `macrorep_test` on the
compose database, created on first use, so start it first (`docker compose up -d
postgres`). `TEST_DATABASE_URL` picks another database; its name must end in `_test`
(anything else is refused), since its `public` schema is wiped before every test. In
parallel, each process gets its own database beside it (`macrorep_gw0_test`, ...).

CI (`.github/workflows/ci.yml`) runs on every push to `main` and every pull request:
backend lint, type check, migrations (upgrade, model check, downgrade and upgrade again)
and tests on PostgreSQL 17; frontend lint, type check, tests and build;
the end-to-end tests (`frontend/e2e`) against this backend on PostgreSQL; and a build of
the production backend image.
