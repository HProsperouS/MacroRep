UV ?= uv

.PHONY: dev dev-down dev-logs web-install web-dev-local web-build web-lint backend-install backend-db-start backend-db-stop backend-db-upgrade backend-dev-local backend-lint backend-typecheck backend-test backend-check

dev:
	docker compose up --build

dev-down:
	docker compose down

dev-logs:
	docker compose logs -f frontend backend

web-install:
	npm --prefix frontend ci

web-dev-local:
	npm --prefix frontend run dev

web-build:
	npm --prefix frontend run build

web-lint:
	npm --prefix frontend run lint

backend-install:
	$(UV) sync --project backend --locked

backend-db-start:
	docker compose up -d --wait postgres

backend-db-stop:
	docker compose stop postgres

backend-db-upgrade:
	$(UV) run --project backend --locked alembic -c backend/alembic.ini upgrade head

backend-dev-local: backend-db-start backend-db-upgrade
	$(UV) run --project backend --locked uvicorn app.main:app --app-dir backend --reload --port 8000

backend-lint:
	$(UV) run --project backend --locked ruff check backend/app backend/migrations backend/tests

backend-typecheck:
	$(UV) run --project backend --locked mypy --config-file backend/pyproject.toml backend/app

backend-test:
	$(UV) run --project backend --locked pytest backend/tests

backend-check: backend-lint backend-typecheck backend-test
