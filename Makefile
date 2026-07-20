# Atom — common tasks for contributors.
# Run `make help` to see everything. These wrap the canonical scripts under
# scripts/ and the E2E suite; no behavior of their own.

VENV       ?= backend/venv/bin/python
PY         ?= $(VENV)
PYTEST     ?= $(VENV) -m pytest
PORT       ?= 8001
FE_PORT    ?= 3001
PYTHONPATH := $(PWD):$(PWD)/backend

.DEFAULT_GOAL := help

.PHONY: help
help: ## Show this help
	@awk 'BEGIN {FS = ":.*##"; printf "Usage: make \033[36m<target>\033[0m\n\n"} \
	  /^[a-zA-Z_-]+:.*?##/ { printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2 }' $(MAKEFILE_LIST)

# -------------------------------------------------------------------
# Setup
# -------------------------------------------------------------------
.PHONY: setup
setup: ## One-shot dev bootstrap: venv, backend deps, frontend deps, .env
	@bash scripts/quickstart.sh

# -------------------------------------------------------------------
# Run (the FULL app — main_api_app, the real feature surface)
# -------------------------------------------------------------------
.PHONY: backend frontend dev
backend: ## Run the full backend (main_api_app) on :$(PORT)
	PYTHONPATH=$(PYTHONPATH) DISABLE_AUTH_RATE_LIMIT=1 \
	  $(PY) -m uvicorn main_api_app:app --reload --port $(PORT)

frontend: ## Run the frontend dev server on :$(FE_PORT)
	cd frontend-nextjs && npm run dev -- -p $(FE_PORT)

dev: ## Run backend + frontend together (requires tmux or two terminals)
	@bash scripts/dev.sh

# -------------------------------------------------------------------
# Tests
# -------------------------------------------------------------------
.PHONY: test test-e2e test-backend
test-backend: ## Run the backend unit tests
	cd backend && $(PYTEST) tests/ -q --tb=short

test-e2e: ## Run the E2E journey suite (needs backend on :$(PORT) + frontend on :$(FE_PORT))
	cd backend/tests/e2e_ui && PLAYWRIGHT_NODEJS_PATH=$$(which node) \
	  ../../venv/bin/python -m pytest tests/test_journey_*.py tests/test_user_journey.py -v

test: test-backend ## Alias for the fast backend tests

# -------------------------------------------------------------------
# Docker
# -------------------------------------------------------------------
.PHONY: docker-build docker-run docker-e2e
docker-build: ## Build the dual-app image
	docker build -t atom:latest \
	  --build-arg NEXT_PUBLIC_API_URL=http://localhost:8000 .

docker-run: ## Run the dual-app image (frontend :3000, backend :8000)
	docker run --rm -p 3000:3000 -p 8000:8000 \
	  -e DATABASE_URL="sqlite:///atom.db" \
	  -e SECRET_KEY=$$(openssl rand -base64 32) \
	  -e ENVIRONMENT=development \
	  atom:latest

docker-e2e: ## Bring up the E2E Docker stack (frontend :3001, backend :8001, db :5434)
	@bash scripts/start-e2e-env.sh

docker-e2e-down: ## Tear down the E2E Docker stack
	@bash scripts/stop-e2e-env.sh

# -------------------------------------------------------------------
# DB
# -------------------------------------------------------------------
.PHONY: migrate
migrate: ## Run the SQLite migration helper
	@$(PY) scripts/utils/migrate_db.py
