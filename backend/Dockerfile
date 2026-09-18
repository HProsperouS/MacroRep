FROM ghcr.io/astral-sh/uv:0.12.13 AS uv

FROM python:3.12-slim AS base

COPY --from=uv /uv /uvx /bin/

RUN groupadd --system --gid 10001 app && \
    useradd --system --uid 10001 --gid app --home-dir /nonexistent app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/macrorep-venv \
    PATH="/opt/macrorep-venv/bin:$PATH"

WORKDIR /srv/backend

COPY backend/pyproject.toml backend/uv.lock backend/README.md backend/alembic.ini ./
COPY backend/app ./app
COPY backend/migrations ./migrations

FROM base AS development

RUN uv sync --locked

USER app

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

FROM base AS production

RUN uv sync --locked --no-dev --no-editable

USER app

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
