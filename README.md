# MacroRep

MacroRep: An Adaptive Nutrition and Workout Tracking Platform Powered by Multi-Agent AI.

- `frontend/` — React 19 + Vite + TypeScript SPA
- `backend/` — FastAPI modular monolith (see `backend/README.md` for its internal structure and design notes)
- `docs/plan.md` — the project plan / brief

## Quick start (Docker — recommended)

This is the standard way to run the whole stack. **No `.env` file needed** —
`compose.yaml` already sets everything the containers need.

Requires [Docker Desktop](https://www.docker.com/products/docker-desktop/) and `make`.

```bash
make dev
# or directly: docker compose up --build
```

This builds and starts 3 containers:

| Container  | What it does                                    | URL                          |
| ---------- | ------------------------------------------------ | ----------------------------- |
| `frontend` | Vite dev server (hot reload)                     | http://localhost:5173         |
| `backend`  | FastAPI + Uvicorn (hot reload), runs migrations on start | http://localhost:8000/docs |
| `postgres` | PostgreSQL 17                                    | localhost:5432 (for a DB client) |

On first boot, the backend seeds one demo account so there's something to look
at immediately:

- **Email:** `alex.tan@example.com`
- **Password:** `macrorep-demo`

Open http://localhost:5173, sign in with that account (or register your own —
registration works for real, against the real database).

Stop everything with `make dev-down` (or `docker compose down`). Data persists
in a Docker volume between runs; to wipe it and reseed from scratch:
`docker compose down -v`.

### Common issues

- **Port already in use** (5173, 8000, or 5432): something else on your
  machine is using that port. Stop it, or edit the `ports:` mapping in
  `compose.yaml`.
- **Frontend can't reach the backend**: make sure the `backend` container is
  healthy (`docker compose ps`) — the frontend waits for it, but a failed
  migration can leave it unhealthy. Check with `docker compose logs backend`.

## Running services individually (without Docker)

Only needed if you're debugging one service in isolation, or don't want to
run Docker at all. Each service needs its own `.env`, since outside Docker
there's no `compose.yaml` to inject config for you.

**Backend** — needs Python 3.12 and [uv](https://docs.astral.sh/uv/), plus a
reachable Postgres (or use SQLite for a zero-install quick start). See
`backend/README.md` for full instructions; the short version:

```bash
cd backend
cp .env.example .env
uv sync
uv run alembic upgrade head   # or set AUTO_CREATE_SCHEMA=true in .env to skip this
uv run uvicorn app.main:app --reload --port 8000
```

**Frontend** — needs Node.js. A `.env` isn't strictly required (it falls back
to `http://127.0.0.1:8000` for the backend), but copy the example if you want
to point it somewhere else:

```bash
cd frontend
cp .env.example .env   # optional
npm install
npm run dev
```

## Project status

See `docs/plan.md` for the full scope, priorities, and multi-agent coach
design. `backend/README.md` documents which parts of that plan are
implemented, which are deliberately simplified for now (e.g. the coach's
proposal-generation pipeline is a rule-based placeholder, not the real
multi-agent system), and why.
