.PHONY: help up down logs simulate dbt-run dbt-test dbt-docs dashboard clean

# ─────────────────────────────────────────
# Load .env
# ─────────────────────────────────────────
ifneq (,$(wildcard .env))
  include .env
  export
endif

help: ## Show available commands
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
	| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ─────────────────────────────────────────
# Docker
# ─────────────────────────────────────────
up: ## Start all services
	docker compose up -d
	@echo "✅ Services started"
	@echo "   Airflow  → http://localhost:8080 (admin/admin)"
	@echo "   Dashboard → http://localhost:8501"

down: ## Stop all services
	docker compose down

logs: ## Follow logs for all services
	docker compose logs -f

restart: ## Restart all services
	docker compose down && docker compose up -d

# ─────────────────────────────────────────
# Simulator
# ─────────────────────────────────────────
simulate: ## Run trade simulator once
	docker compose run --rm simulator

# ─────────────────────────────────────────
# dbt
# ─────────────────────────────────────────
dbt-deps: ## Install dbt packages
	cd dbt && dbt deps

dbt-debug: ## Test dbt connection
	cd dbt && dbt debug

dbt-run: ## Run all dbt models
	cd dbt && dbt run

dbt-test: ## Run all dbt tests
	cd dbt && dbt test

dbt-run-test: ## Run dbt models then tests
	cd dbt && dbt run && dbt test

dbt-freshness: ## Check source freshness
	cd dbt && dbt source freshness

dbt-docs: ## Generate and serve dbt docs
	cd dbt && dbt docs generate && dbt docs serve

dbt-lint: ## Lint SQL with sqlfluff
	cd dbt && sqlfluff lint models/ --dialect postgres

# ─────────────────────────────────────────
# Python
# ─────────────────────────────────────────
lint: ## Lint Python with ruff
	ruff check simulator/ dashboard/

# ─────────────────────────────────────────
# Full pipeline (local)
# ─────────────────────────────────────────
pipeline: ## Run full pipeline locally (simulate → dbt run → dbt test)
	@echo "▶ Running simulator..."
	$(MAKE) simulate
	@echo "▶ Running dbt..."
	$(MAKE) dbt-run-test
	@echo "✅ Pipeline complete"

# ─────────────────────────────────────────
# Cleanup
# ─────────────────────────────────────────
clean: ## Remove dbt artifacts
	rm -rf dbt/target dbt/dbt_packages dbt/logs

reset: ## Reset all volumes and restart fresh (WARNING: deletes all data)
	@echo "⚠️  Resetting all volumes — all data will be lost"
	docker compose down -v
	docker compose up -d
	@echo "⏳ Waiting for PostgreSQL to be ready..."
	@sleep 20
	@docker exec postgres-app psql -U $(APP_DB_USER) -d $(APP_DB_NAME) -c "\dt" \
		&& echo "✅ Database ready" \
		|| echo "❌ Database not ready — wait and try 'make simulate'"