.PHONY: help test build integration-up integration-test integration-down integration pre-deploy clean

# Default target
help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

test: ## Run unit tests
	uv run pytest tests/ -v --ignore=tests/integration

build: ## Build Docker images for testing
	docker compose -f docker-compose.test.yaml build

integration-up: ## Start integration test containers
	docker compose -f docker-compose.test.yaml up -d
	@echo "Waiting for services to be ready..."
	@sleep 5

integration-test: ## Run integration tests (containers must be up)
	uv run pytest tests/integration/ -v

integration-down: ## Stop and remove test containers
	docker compose -f docker-compose.test.yaml down -v

integration: build integration-up ## Full integration cycle (build, up, test, down)
	@$(MAKE) integration-test || ($(MAKE) integration-down && exit 1)
	@$(MAKE) integration-down

pre-deploy: test integration ## Full pre-deployment pipeline (unit tests + integration)
	@echo "Pre-deployment checks passed!"

clean: ## Remove all test artifacts and containers
	docker compose -f docker-compose.test.yaml down -v --rmi local 2>/dev/null || true
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
