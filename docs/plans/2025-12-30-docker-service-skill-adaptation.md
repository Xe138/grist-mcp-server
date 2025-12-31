# Docker Service Architecture Adaptation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Adapt grist-mcp to follow the docker-service-architecture skill guidelines for better test isolation, environment separation, and CI/CD readiness.

**Architecture:** Single-service project pattern with 2-stage testing (unit → integration), environment-specific deploy configs (dev/test/prod), and branch-isolated test infrastructure.

**Tech Stack:** Docker Compose, Make, Python/pytest, bash scripts

---

## Current State Analysis

**What we have:**
- Single service (grist-mcp) with mock server for testing
- 2-stage testing: unit tests (41) + integration tests (2)
- docker-compose.test.yaml at project root
- docker-compose.yaml for production at root
- Basic Makefile with pre-deploy target

**Gaps vs. Skill Guidelines:**

| Area | Current | Skill Guideline |
|------|---------|-----------------|
| Directory structure | Flat docker-compose files at root | `deploy/{dev,test,prod}/` directories |
| Test organization | `tests/*.py` + `tests/integration/` | `tests/unit/` + `tests/integration/` |
| Port allocation | Fixed (3000, 8484) | Dynamic with discovery |
| Branch isolation | None | TEST_INSTANCE_ID from git branch |
| Container naming | Default | Instance-based (`-${TEST_INSTANCE_ID}`) |
| Test storage | Default volumes | tmpfs for ephemeral |
| depends_on | `service_started` | `service_healthy` |

---

## Task 1: Restructure Tests Directory

**Files:**
- Move: `tests/test_*.py` → `tests/unit/test_*.py`
- Keep: `tests/integration/` as-is
- Create: `tests/unit/__init__.py`

**Step 1: Create unit test directory and move files**

```bash
mkdir -p tests/unit
mv tests/test_*.py tests/unit/
touch tests/unit/__init__.py
```

**Step 2: Update pyproject.toml testpaths**

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests/unit", "tests/integration"]
```

**Step 3: Update Makefile test target**

```makefile
test: ## Run unit tests
	uv run pytest tests/unit/ -v
```

**Step 4: Verify tests still pass**

```bash
uv run pytest tests/unit/ -v
uv run pytest tests/integration/ -v --ignore=tests/integration
```

**Step 5: Commit**

```bash
git add tests/ pyproject.toml Makefile
git commit -m "refactor: organize tests into unit/ and integration/ directories"
```

---

## Task 2: Create Deploy Directory Structure

**Files:**
- Create: `deploy/dev/docker-compose.yml`
- Create: `deploy/dev/.env.example`
- Create: `deploy/test/docker-compose.yml`
- Create: `deploy/prod/docker-compose.yml`
- Create: `deploy/prod/.env.example`
- Delete: `docker-compose.yaml`, `docker-compose.test.yaml` (after migration)

**Step 1: Create deploy directory structure**

```bash
mkdir -p deploy/{dev,test,prod}
```

**Step 2: Create deploy/dev/docker-compose.yml**

```yaml
# Development environment - hot reload, persistent data
services:
  grist-mcp:
    build:
      context: ../..
      dockerfile: Dockerfile
    ports:
      - "${PORT:-3000}:3000"
    volumes:
      - ../../src:/app/src:ro
      - ../../config.yaml:/app/config.yaml:ro
    env_file:
      - .env
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:3000/health')"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 60s
```

**Step 3: Create deploy/dev/.env.example**

```bash
PORT=3000
GRIST_MCP_TOKEN=your-token-here
CONFIG_PATH=/app/config.yaml
```

**Step 4: Create deploy/test/docker-compose.yml**

```yaml
# Test environment - ephemeral, branch-isolated
services:
  grist-mcp:
    build:
      context: ../..
      dockerfile: Dockerfile
    container_name: grist-mcp-test-${TEST_INSTANCE_ID:-default}
    ports:
      - "3000"  # Dynamic port
    environment:
      - CONFIG_PATH=/app/config.yaml
      - GRIST_MCP_TOKEN=test-token
      - PORT=3000
    volumes:
      - ../../tests/integration/config.test.yaml:/app/config.yaml:ro
    depends_on:
      mock-grist:
        condition: service_healthy
    networks:
      - test-net
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:3000/health')"]
      interval: 5s
      timeout: 5s
      retries: 10
      start_period: 10s

  mock-grist:
    build:
      context: ../../tests/integration/mock_grist
    container_name: mock-grist-test-${TEST_INSTANCE_ID:-default}
    ports:
      - "8484"  # Dynamic port
    environment:
      - PORT=8484
    networks:
      - test-net
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8484/health')"]
      interval: 5s
      timeout: 5s
      retries: 10
      start_period: 10s

networks:
  test-net:
    name: grist-mcp-test-${TEST_INSTANCE_ID:-default}
    driver: bridge
```

**Step 5: Create deploy/prod/docker-compose.yml**

```yaml
# Production environment - resource limits, logging, restart policy
services:
  grist-mcp:
    build:
      context: ../..
      dockerfile: Dockerfile
    ports:
      - "${PORT:-3000}:3000"
    volumes:
      - ./config.yaml:/app/config.yaml:ro
    env_file:
      - .env
    restart: unless-stopped
    deploy:
      resources:
        limits:
          memory: 512M
          cpus: "1"
        reservations:
          memory: 128M
    logging:
      driver: "json-file"
      options:
        max-size: "50m"
        max-file: "5"
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:3000/health')"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 60s
```

**Step 6: Create deploy/prod/.env.example**

```bash
PORT=3000
GRIST_MCP_TOKEN=your-production-token
CONFIG_PATH=/app/config.yaml
```

**Step 7: Verify test compose works**

```bash
cd deploy/test
TEST_INSTANCE_ID=manual docker compose up -d --build
docker compose ps
docker compose down -v
```

**Step 8: Remove old compose files and commit**

```bash
rm docker-compose.yaml docker-compose.test.yaml
git add deploy/
git rm docker-compose.yaml docker-compose.test.yaml
git commit -m "refactor: move docker-compose files to deploy/ directory structure"
```

---

## Task 3: Add Test Isolation Scripts

**Files:**
- Create: `scripts/get-test-instance-id.sh`
- Create: `scripts/run-integration-tests.sh`

**Step 1: Create scripts directory**

```bash
mkdir -p scripts
```

**Step 2: Create get-test-instance-id.sh**

```bash
#!/bin/bash
# scripts/get-test-instance-id.sh
# Generate a unique instance ID from git branch for parallel test isolation

BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "unknown")
# Sanitize: replace non-alphanumeric with dash, limit length
echo "$BRANCH" | sed 's/[^a-zA-Z0-9]/-/g' | cut -c1-20
```

**Step 3: Create run-integration-tests.sh**

```bash
#!/bin/bash
# scripts/run-integration-tests.sh
# Run integration tests with branch isolation and dynamic port discovery
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Get branch-based instance ID
TEST_INSTANCE_ID=$("$SCRIPT_DIR/get-test-instance-id.sh")
export TEST_INSTANCE_ID

echo "Test instance ID: $TEST_INSTANCE_ID"

# Start containers
cd "$PROJECT_ROOT/deploy/test"
docker compose up -d --build --wait

# Discover dynamic ports
GRIST_MCP_PORT=$(docker compose port grist-mcp 3000 | cut -d: -f2)
MOCK_GRIST_PORT=$(docker compose port mock-grist 8484 | cut -d: -f2)

echo "grist-mcp available at: http://localhost:$GRIST_MCP_PORT"
echo "mock-grist available at: http://localhost:$MOCK_GRIST_PORT"

# Export for tests
export GRIST_MCP_URL="http://localhost:$GRIST_MCP_PORT"
export MOCK_GRIST_URL="http://localhost:$MOCK_GRIST_PORT"

# Run tests
cd "$PROJECT_ROOT"
TEST_EXIT=0
uv run pytest tests/integration/ -v || TEST_EXIT=$?

# Cleanup
cd "$PROJECT_ROOT/deploy/test"
docker compose down -v

exit $TEST_EXIT
```

**Step 4: Make scripts executable**

```bash
chmod +x scripts/get-test-instance-id.sh
chmod +x scripts/run-integration-tests.sh
```

**Step 5: Verify scripts work**

```bash
./scripts/get-test-instance-id.sh
./scripts/run-integration-tests.sh
```

**Step 6: Commit**

```bash
git add scripts/
git commit -m "feat: add test isolation scripts with dynamic port discovery"
```

---

## Task 4: Update Integration Tests for Dynamic Ports

**Files:**
- Modify: `tests/integration/conftest.py`

**Step 1: Update conftest.py to use environment variables**

```python
"""Fixtures for integration tests."""

import os
import time

import httpx
import pytest


# Use environment variables for dynamic port discovery
GRIST_MCP_URL = os.environ.get("GRIST_MCP_URL", "http://localhost:3000")
MOCK_GRIST_URL = os.environ.get("MOCK_GRIST_URL", "http://localhost:8484")
MAX_WAIT_SECONDS = 30


def wait_for_service(url: str, timeout: int = MAX_WAIT_SECONDS) -> bool:
    """Wait for a service to become healthy."""
    start = time.time()
    while time.time() - start < timeout:
        try:
            response = httpx.get(f"{url}/health", timeout=2.0)
            if response.status_code == 200:
                return True
        except httpx.RequestError:
            pass
        time.sleep(0.5)
    return False


@pytest.fixture(scope="session")
def services_ready():
    """Ensure both services are healthy before running tests."""
    if not wait_for_service(MOCK_GRIST_URL):
        pytest.fail(f"Mock Grist server not ready at {MOCK_GRIST_URL}")
    if not wait_for_service(GRIST_MCP_URL):
        pytest.fail(f"grist-mcp server not ready at {GRIST_MCP_URL}")
    return True
```

**Step 2: Update test files to use environment URLs**

In `tests/integration/test_mcp_protocol.py` and `tests/integration/test_tools_integration.py`:

```python
import os

GRIST_MCP_URL = os.environ.get("GRIST_MCP_URL", "http://localhost:3000")
MOCK_GRIST_URL = os.environ.get("MOCK_GRIST_URL", "http://localhost:8484")
```

**Step 3: Run tests to verify**

```bash
./scripts/run-integration-tests.sh
```

**Step 4: Commit**

```bash
git add tests/integration/
git commit -m "feat: support dynamic ports via environment variables in tests"
```

---

## Task 5: Update Makefile

**Files:**
- Modify: `Makefile`

**Step 1: Rewrite Makefile with new structure**

```makefile
.PHONY: help test test-unit test-integration build dev-up dev-down integration pre-deploy clean

VERBOSE ?= 0
PYTEST_ARGS := $(if $(filter 1,$(VERBOSE)),-v,-q)

# Default target
help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# Testing
test: test-unit ## Run all tests (unit only by default)

test-unit: ## Run unit tests
	uv run pytest tests/unit/ $(PYTEST_ARGS)

test-integration: ## Run integration tests (starts/stops containers)
	./scripts/run-integration-tests.sh

# Docker
build: ## Build Docker image
	docker build -t grist-mcp:latest .

dev-up: ## Start development environment
	cd deploy/dev && docker compose up -d --build

dev-down: ## Stop development environment
	cd deploy/dev && docker compose down

# Pre-deployment
pre-deploy: test-unit test-integration ## Full pre-deployment pipeline
	@echo "Pre-deployment checks passed!"

# Cleanup
clean: ## Remove test artifacts and containers
	cd deploy/test && docker compose down -v --rmi local 2>/dev/null || true
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
```

**Step 2: Verify Makefile targets**

```bash
make help
make test-unit
make test-integration
make pre-deploy
```

**Step 3: Commit**

```bash
git add Makefile
git commit -m "refactor: update Makefile for new deploy/ structure"
```

---

## Task 6: Update CLAUDE.md

**Files:**
- Modify: `CLAUDE.md`

**Step 1: Update commands section**

Add to CLAUDE.md:

```markdown
## Commands

```bash
# Run unit tests
make test-unit
# or: uv run pytest tests/unit/ -v

# Run integration tests (manages containers automatically)
make test-integration
# or: ./scripts/run-integration-tests.sh

# Full pre-deploy pipeline
make pre-deploy

# Development environment
make dev-up    # Start
make dev-down  # Stop

# Build Docker image
make build
```

## Project Structure

```
src/grist_mcp/       # Source code
tests/
├── unit/            # Unit tests (no containers)
└── integration/     # Integration tests (with Docker)
deploy/
├── dev/             # Development docker-compose
├── test/            # Test docker-compose (ephemeral)
└── prod/            # Production docker-compose
scripts/             # Test automation scripts
```
```

**Step 2: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: update CLAUDE.md with new project structure"
```

---

## Task 7: Final Verification

**Step 1: Run full pre-deploy pipeline**

```bash
make pre-deploy
```

Expected output:
- Unit tests pass (41 tests)
- Integration tests pass with branch isolation
- Containers cleaned up

**Step 2: Test parallel execution (optional)**

```bash
# In terminal 1
git checkout -b test-branch-1
make test-integration &

# In terminal 2
git checkout -b test-branch-2
make test-integration &
```

Both should run without port conflicts.

**Step 3: Commit final verification**

```bash
git add .
git commit -m "chore: complete docker-service-architecture adaptation"
```

---

## Summary of Changes

| Before | After |
|--------|-------|
| `tests/test_*.py` | `tests/unit/test_*.py` |
| `docker-compose.yaml` | `deploy/dev/docker-compose.yml` |
| `docker-compose.test.yaml` | `deploy/test/docker-compose.yml` |
| (none) | `deploy/prod/docker-compose.yml` |
| Fixed ports (3000, 8484) | Dynamic ports with discovery |
| No branch isolation | TEST_INSTANCE_ID from git branch |
| `service_started` | `service_healthy` |
| Basic Makefile | Environment-aware with VERBOSE support |

## Benefits

1. **Parallel testing** - Multiple branches can run tests simultaneously
2. **Environment parity** - Clear dev/test/prod separation
3. **CI/CD ready** - Scripts work in automated pipelines
4. **Faster feedback** - Dynamic ports eliminate conflicts
5. **Cleaner structure** - Tests and deploys clearly organized
