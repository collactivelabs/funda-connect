.PHONY: help up down build logs shell-backend shell-frontend migrate migrate-create lint test promote-admin payfast-tunnel payfast-webhook-path

# ── Config ────────────────────────────────────────────────────
BACKEND_SERVICE = backend
FRONTEND_SERVICE = frontend

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ── Docker Compose ───────────────────────────────────────────
up: ## Start all services
	docker compose up -d

up-build: ## Build and start all services
	docker compose up -d --build

down: ## Stop all services
	docker compose down

down-volumes: ## Stop all services and remove volumes
	docker compose down -v

build: ## Build all service images
	docker compose build

logs: ## Follow logs for all services
	docker compose logs -f

logs-backend: ## Follow backend logs
	docker compose logs -f $(BACKEND_SERVICE)

logs-frontend: ## Follow frontend logs
	docker compose logs -f $(FRONTEND_SERVICE)

restart-backend: ## Restart backend service
	docker compose restart $(BACKEND_SERVICE)

# ── Database ─────────────────────────────────────────────────
migrate: ## Run all pending Alembic migrations
	docker compose exec $(BACKEND_SERVICE) alembic upgrade head

migrate-create: ## Create a new migration (usage: make migrate-create MSG="add users table")
	docker compose exec $(BACKEND_SERVICE) alembic revision --autogenerate -m "$(MSG)"

migrate-down: ## Roll back the last migration
	docker compose exec $(BACKEND_SERVICE) alembic downgrade -1

db-shell: ## Open PostgreSQL shell
	docker compose exec db psql -U fundaconnect -d fundaconnect

# ── Backend ──────────────────────────────────────────────────
shell-backend: ## Open a shell in the backend container
	docker compose exec $(BACKEND_SERVICE) bash

lint-backend: ## Run ruff linter on backend
	docker compose exec $(BACKEND_SERVICE) ruff check app/

format-backend: ## Format backend code with ruff
	docker compose exec $(BACKEND_SERVICE) ruff format app/

typecheck-backend: ## Run mypy type checking on backend
	docker compose exec $(BACKEND_SERVICE) mypy app/

test-backend: ## Run backend tests
	docker compose exec $(BACKEND_SERVICE) pytest tests/ -v

promote-admin: ## Promote an existing user to admin (usage: make promote-admin EMAIL=you@example.com)
	@test -n "$(EMAIL)" || (echo "Usage: make promote-admin EMAIL=labs@example.com" && exit 1)
	docker compose exec $(BACKEND_SERVICE) python -m app.scripts.promote_admin --email "$(EMAIL)"

payfast-tunnel: ## Start an ngrok tunnel for PayFast ITN callbacks on backend port 8000
	ngrok http 8000

payfast-webhook-path: ## Show the public PayFast ITN path to append to your tunnel URL
	@echo "Set PAYFAST_NOTIFY_URL to:"
	@echo "  https://<your-ngrok-domain>/api/v1/bookings/payfast/itn"

# ── Frontend ─────────────────────────────────────────────────
shell-frontend: ## Open a shell in the frontend container
	docker compose exec $(FRONTEND_SERVICE) sh

lint-frontend: ## Run ESLint on frontend
	docker compose exec $(FRONTEND_SERVICE) pnpm lint

typecheck-frontend: ## Run TypeScript type check on frontend
	docker compose exec $(FRONTEND_SERVICE) pnpm typecheck

test-frontend: ## Run frontend tests
	docker compose exec $(FRONTEND_SERVICE) pnpm test

# ── Combined ─────────────────────────────────────────────────
lint: lint-backend lint-frontend ## Lint all services

test: test-backend test-frontend ## Test all services

# ── Setup ────────────────────────────────────────────────────
setup: ## First-time project setup
	@cp -n .env.example .env || true
	@echo "✅  .env created from .env.example — update values before running"
	@$(MAKE) up-build
	@sleep 5
	@$(MAKE) migrate
	@echo "✅  FundaConnect is running!"
	@echo "   Frontend: http://localhost:3001"
	@echo "   Backend:  http://localhost:8000/docs"
	@echo "   Flower:   http://localhost:5555"
