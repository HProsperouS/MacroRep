# MacroRep backend

FastAPI modular monolith serving the endpoints the frontend already calls (see
`frontend/src/api/*.ts`): profile, food log, workouts, bodyweight, progress,
and the coach check-in flow.

## Structure

```text
backend/
├── app/
│   ├── main.py            # FastAPI entry point and middleware
│   ├── demo_seed.py        # idempotent local demo seed
│   ├── core/                # typed configuration and DB session
│   ├── shared/               # logging, correlation IDs, persistence base, camelCase schema base
│   ├── identity/              # current-actor resolution (self-issued JWT or local preview header)
│   ├── auth/                   # registration, login, refresh-token rotation, logout
│   ├── profile/                 # fitness profile and nutrition targets
│   ├── food/                     # food catalog and daily food log
│   ├── workout/                    # exercise catalog, weekly plan, logged sessions
│   ├── body/                        # weigh-ins and trend-weight calculation
│   ├── progress/                     # read-model composing the above into dashboard charts
│   ├── analytics/                     # deterministic nutrition, training and weight formulas
│   ├── coach/                          # check-ins, proposals, chat; agents/ is the LangGraph flow
│   └── health/                          # liveness/readiness/version
├── migrations/             # Alembic schema migrations
├── tests/                  # API, validation and formula tests (in-memory SQLite, or Postgres)
├── pyproject.toml
└── Dockerfile
```

Each domain normally owns `models.py`, `schemas.py`, `repository.py`,
`service.py`, and `router.py`.

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
  see that module's docstrings. Sign-in and sign-up attempts are limited
  (`app/shared/rate_limit.py`): in 15 minutes, 5 wrong passwords for an account
  from one address (so someone else guessing can't lock its owner out) and 30
  sign-ins per address; 50 wrong passwords for an account from anywhere and 10
  sign-ups per address an hour. Coach Chat allows 30 questions per user an
  hour, since each is a paid model call. Then 429 with `Retry-After`. `PREVIEW_AUTH_ENABLED` (on by default outside
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
uv run pytest --cov            # with branch coverage; fails below 90%
```

Tests use in-memory SQLite by default. To run them on PostgreSQL, as CI also does, point
`TEST_DATABASE_URL` at a separate database whose name ends in `_test` (anything else is
refused): its `public` schema is wiped before every test. With the compose database:

```bash
docker compose exec postgres createdb -U macrorep macrorep_test   # once
TEST_DATABASE_URL=postgresql+psycopg://macrorep:local-development-only@localhost:5432/macrorep_test uv run pytest
```

CI (`.github/workflows/ci.yml`) runs on every push to `main` and every pull request:
backend lint, type check, migrations (upgrade, model check, downgrade and upgrade again)
and tests on both PostgreSQL 17 and SQLite; frontend lint, type check, tests and build;
the end-to-end tests (`frontend/e2e`) against this backend on PostgreSQL; and a build of
the production backend image.
