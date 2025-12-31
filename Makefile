.PHONY: help test test-unit test-integration build dev-up dev-down pre-deploy clean

VERBOSE ?= 0

# Default target
help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# Testing
test: ## Run all tests (unit + integration) with rich progress display
	@uv run python scripts/test-runner.py $(if $(filter 1,$(VERBOSE)),-v)

test-unit: ## Run unit tests only
	@uv run python scripts/test-runner.py --unit-only $(if $(filter 1,$(VERBOSE)),-v)

test-integration: ## Run integration tests only (starts/stops containers)
	@uv run python scripts/test-runner.py --integration-only $(if $(filter 1,$(VERBOSE)),-v)

# Docker
build: ## Build Docker image
	docker build -t grist-mcp:latest .

dev-up: ## Start development environment
	cd deploy/dev && docker compose up -d --build

dev-down: ## Stop development environment
	cd deploy/dev && docker compose down

# Pre-deployment
pre-deploy: test ## Full pre-deployment pipeline
	@echo "Pre-deployment checks passed!"

# Cleanup
clean: ## Remove test artifacts and containers
	cd deploy/test && docker compose down -v --rmi local 2>/dev/null || true
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
