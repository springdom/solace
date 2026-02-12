.PHONY: help setup dev test lint migrate migration clean docker-up docker-down

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ──────────────────────────────────────
# Setup
# ──────────────────────────────────────

setup: ## First-time project setup
	@echo "🔧 Installing dependencies..."
	pip install -e ".[dev]"
	@echo "📋 Copying .env.example to .env..."
	@cp -n .env.example .env 2>/dev/null || true
	@echo "🗄️  Running database migrations..."
	alembic upgrade head
	@echo "✅ Setup complete. Run 'make dev' to start."

# ──────────────────────────────────────
# Development
# ──────────────────────────────────────

dev: ## Start dev server with hot reload
	uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000

dev-worker: ## Start Celery worker (when ready)
	@echo "Worker not yet implemented"

# ──────────────────────────────────────
# Testing
# ──────────────────────────────────────

test: ## Run test suite
	pytest -v --tb=short

test-cov: ## Run tests with coverage
	pytest -v --cov=backend --cov-report=html --cov-report=term

# ──────────────────────────────────────
# Code Quality
# ──────────────────────────────────────

lint: ## Run linters
	ruff check backend/ tests/
	ruff format --check backend/ tests/

format: ## Auto-format code
	ruff check --fix backend/ tests/
	ruff format backend/ tests/

typecheck: ## Run type checker
	mypy backend/

# ──────────────────────────────────────
# Database
# ──────────────────────────────────────

migrate: ## Run pending migrations
	alembic upgrade head

migration: ## Create new migration (usage: make migration m="description")
	alembic revision --autogenerate -m "$(m)"

migrate-down: ## Rollback last migration
	alembic downgrade -1

db-reset: ## Drop and recreate database (DESTRUCTIVE)
	@echo "⚠️  This will destroy all data. Press Ctrl+C to cancel."
	@sleep 3
	alembic downgrade base
	alembic upgrade head

# ──────────────────────────────────────
# Docker
# ──────────────────────────────────────

docker-up: ## Start all services with Docker Compose
	docker compose up -d

docker-down: ## Stop all services
	docker compose down

docker-build: ## Rebuild Docker images
	docker compose build

docker-logs: ## Tail Docker logs
	docker compose logs -f

# ──────────────────────────────────────
# Cleanup
# ──────────────────────────────────────

clean: ## Remove build artifacts and caches
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .mypy_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .ruff_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name htmlcov -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
