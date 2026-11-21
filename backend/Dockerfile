# syntax=docker/dockerfile:1

# Stages:
#   development  what compose runs: every dependency, dev tools included, and --reload
#                (compose mounts backend/ over the code).
#   builder      installs the production dependencies and the app into a virtualenv.
#   production   what's deployed: that virtualenv and the migrations, no uv, no build caches.
#
# Dependencies are installed before the code is copied, so a code change reuses the
# dependency layer; only a change to pyproject.toml or uv.lock reinstalls them.

FROM ghcr.io/astral-sh/uv:0.12.13 AS uv

FROM python:3.12-slim AS base

RUN groupadd --system --gid 10001 app && \
    useradd --system --uid 10001 --gid app --home-dir /nonexistent app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/opt/macrorep-venv \
    PATH="/opt/macrorep-venv/bin:$PATH"

WORKDIR /srv/backend

FROM base AS development

COPY --from=uv /uv /uvx /bin/

COPY backend/pyproject.toml backend/uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-install-project

COPY backend/README.md backend/alembic.ini ./
COPY backend/app ./app
COPY backend/migrations ./migrations
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked

USER app

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

FROM base AS builder

COPY --from=uv /uv /uvx /bin/

COPY backend/pyproject.toml backend/uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-install-project

COPY backend/README.md ./
COPY backend/app ./app
# Not editable: the app is installed into the virtualenv (byte-compiled), so the runtime
# image needs no source tree beside it.
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-editable

FROM base AS production

COPY --from=builder /opt/macrorep-venv /opt/macrorep-venv
# The release's migration task runs `alembic upgrade head` from this same image.
COPY backend/alembic.ini ./
COPY backend/migrations ./migrations

USER app

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
