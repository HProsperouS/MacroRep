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
│   ├── coach/                          # check-ins, proposals, chat (see pipeline.py)
│   └── health/                          # liveness/readiness/version
├── migrations/             # Alembic schema migrations
├── tests/                  # API smoke tests (in-memory SQLite)
├── pyproject.toml
└── Dockerfile
```

Each domain normally owns `models.py`, `schemas.py`, `repository.py`,
`service.py`, and `router.py`.

### Known simplifications vs. a production system

- **Coach AI is a placeholder.** `app/coach/pipeline.py` is a deterministic,
  rule-based stand-in for the multi-agent generation pipeline described in
  the project brief. It produces the same output shape a real pipeline would,
  so the rest of the app can be built against a stable contract; only that
  one function's body needs to change later.
- **No shared-record audit trail.** Unlike a multi-staff CRM, MacroRep
  records are single-owner personal data, so there's no admin/agent role
  hierarchy or soft-delete-with-named-actor trail — just plain
  `created_utc`/`updated_utc` timestamps and owner-scoped queries.
- **Auth is self-issued, not a third-party provider.** `app/auth` implements
  email/password registration and login (Argon2 hashing), a short-lived JWT
  access token, and a rotating refresh token stored as an httpOnly cookie —
  see that module's docstrings. `PREVIEW_AUTH_ENABLED` (on by default outside
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

```bash
uv run ruff check app migrations tests
uv run mypy --config-file pyproject.toml app
uv run pytest
```
