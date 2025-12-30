# Pre-Deployment Test Process Design

## Overview

A pre-deployment test pipeline that runs unit tests, builds Docker images, spins up a test environment, and runs integration tests against the containerized service.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Test Orchestration                        │
│                      (Makefile)                              │
└─────────────────────────────────────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        ▼                   ▼                   ▼
┌──────────────┐   ┌──────────────┐   ┌──────────────────────┐
│  Unit Tests  │   │ Docker Build │   │  Integration Tests   │
│  (pytest)    │   │              │   │  (pytest + MCP SDK)  │
└──────────────┘   └──────────────┘   └──────────────────────┘
                                                │
                                                ▼
                        ┌───────────────────────────────────┐
                        │     docker-compose.test.yaml      │
                        ├───────────────┬───────────────────┤
                        │  grist-mcp    │   mock-grist      │
                        │  (SSE server) │   (Python HTTP)   │
                        └───────────────┴───────────────────┘
```

**Flow:**
1. `make pre-deploy` runs the full pipeline
2. Unit tests run first (fail fast)
3. Docker images build (grist-mcp + mock-grist)
4. docker-compose.test.yaml starts both containers on an isolated network
5. Integration tests connect to grist-mcp via MCP SDK over SSE
6. Mock Grist validates API calls and returns canned responses
7. Teardown happens regardless of test outcome

## Components

### Mock Grist Server

Location: `tests/integration/mock_grist/`

```
tests/integration/mock_grist/
├── Dockerfile
├── server.py          # FastAPI/Starlette app
└── expectations.py    # Request validation logic
```

**Behavior:**
- Runs on port 8484 inside the test network
- Exposes Grist API endpoints: `/api/docs/{docId}/tables`, `/api/docs/{docId}/tables/{tableId}/records`, etc.
- Logs all requests to stdout (visible in test output)
- Returns realistic mock responses based on the endpoint
- Optionally validates request bodies (e.g., correct record format for add_records)

**Configuration via environment:**
- `MOCK_GRIST_STRICT=true` - Fail on unexpected endpoints (default: false, just log warnings)
- Response data is hardcoded but realistic (a few tables, some records)

### Docker Compose Test Configuration

File: `docker-compose.test.yaml`

```yaml
services:
  grist-mcp:
    build: .
    ports:
      - "3000:3000"
    environment:
      - CONFIG_PATH=/app/config.yaml
      - GRIST_MCP_TOKEN=test-token
    volumes:
      - ./tests/integration/config.test.yaml:/app/config.yaml:ro
    depends_on:
      mock-grist:
        condition: service_started
    networks:
      - test-net

  mock-grist:
    build: tests/integration/mock_grist
    ports:
      - "8484:8484"
    networks:
      - test-net

networks:
  test-net:
    driver: bridge
```

**Key points:**
- Isolated network so containers can communicate by service name
- grist-mcp waits for mock-grist to start
- Ports exposed to host so pytest can connect from outside
- No volumes for secrets - everything is test fixtures

### Integration Tests

Location: `tests/integration/`

```
tests/integration/
├── conftest.py              # Fixtures: MCP client, wait_for_ready
├── test_mcp_protocol.py     # SSE connection, tool listing, basic protocol
├── test_tools_integration.py # Call each tool, verify Grist API interactions
├── config.test.yaml         # Test configuration for grist-mcp
└── mock_grist/              # Mock server
```

**conftest.py fixtures:**
```python
@pytest.fixture
async def mcp_client():
    """Connect to grist-mcp via SSE and yield the client."""
    async with sse_client("http://localhost:3000/sse") as client:
        yield client

@pytest.fixture(scope="session")
def wait_for_services():
    """Block until both containers are healthy."""
    # Poll http://localhost:3000/health and http://localhost:8484/health
```

**Test coverage:**
- `test_list_tools` - Connect, call `list_tools`, verify all expected tools returned
- `test_list_documents` - Call `list_documents` tool, verify response structure
- `test_get_records` - Call `get_records`, verify mock-grist received correct API call
- `test_add_records` - Call `add_records`, verify request body sent to mock-grist

### Makefile Orchestration

File: `Makefile`

```makefile
.PHONY: test build integration pre-deploy clean help

help:                      ## Show this help
test:                      ## Run unit tests
build:                     ## Build Docker images
integration-up:            ## Start integration test containers
integration-test:          ## Run integration tests (containers must be up)
integration-down:          ## Stop and remove test containers
integration:               ## Full integration cycle (up, test, down)
pre-deploy:                ## Full pre-deployment pipeline
clean:                     ## Remove all test artifacts
```

**Key targets:**
- `make test` - `uv run pytest tests/ -v --ignore=tests/integration`
- `make build` - `docker compose -f docker-compose.test.yaml build`
- `make integration-up` - `docker compose -f docker-compose.test.yaml up -d`
- `make integration-test` - `uv run pytest tests/integration/ -v`
- `make integration-down` - `docker compose -f docker-compose.test.yaml down -v`
- `make integration` - Runs up, test, down (with proper cleanup on failure)
- `make pre-deploy` - Runs test, build, integration in sequence

**Failure handling:**
- `integration` target uses trap or `||` pattern to ensure `down` runs even if tests fail
- Exit codes propagate so CI can detect failures

## Files to Create

| File | Purpose |
|------|---------|
| `Makefile` | Orchestration with help, test, build, integration, pre-deploy targets |
| `docker-compose.test.yaml` | grist-mcp + mock-grist on isolated network |
| `tests/integration/config.test.yaml` | Test configuration pointing to mock-grist |
| `tests/integration/conftest.py` | MCP client fixtures |
| `tests/integration/test_mcp_protocol.py` | Protocol compliance tests |
| `tests/integration/test_tools_integration.py` | Tool call validation tests |
| `tests/integration/mock_grist/Dockerfile` | Slim Python image |
| `tests/integration/mock_grist/server.py` | FastAPI mock server |

## Usage

```bash
make pre-deploy    # Full pipeline
make integration   # Just integration tests
make test          # Just unit tests
```
