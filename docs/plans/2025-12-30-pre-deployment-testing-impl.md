# Pre-Deployment Testing Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Create a pre-deployment test pipeline with Makefile orchestration, mock Grist server, and MCP protocol integration tests.

**Architecture:** Makefile orchestrates unit tests, Docker builds, and integration tests. Integration tests use the MCP Python SDK to connect to the containerized grist-mcp server, which talks to a mock Grist API server. Both run in docker-compose on an isolated network.

**Tech Stack:** Python 3.14, pytest, MCP SDK, Starlette (mock server), Docker Compose, Make

---

## Task 1: Add Health Endpoint to grist-mcp

The integration tests need to poll for service readiness. Add a `/health` endpoint.

**Files:**
- Modify: `src/grist_mcp/main.py:42-47`

**Step 1: Add health endpoint to main.py**

In `src/grist_mcp/main.py`, add a health route to the Starlette app:

```python
from starlette.responses import JSONResponse

async def handle_health(request):
    return JSONResponse({"status": "ok"})
```

And add the route:

```python
return Starlette(
    routes=[
        Route("/health", endpoint=handle_health),
        Route("/sse", endpoint=handle_sse),
        Route("/messages", endpoint=handle_messages, methods=["POST"]),
    ]
)
```

**Step 2: Run existing tests**

Run: `uv run pytest tests/test_server.py -v`
Expected: PASS (health endpoint doesn't break existing tests)

**Step 3: Commit**

```bash
git add src/grist_mcp/main.py
git commit -m "feat: add /health endpoint for service readiness checks"
```

---

## Task 2: Create Mock Grist Server

**Files:**
- Create: `tests/integration/mock_grist/__init__.py`
- Create: `tests/integration/mock_grist/server.py`
- Create: `tests/integration/mock_grist/Dockerfile`
- Create: `tests/integration/mock_grist/requirements.txt`

**Step 1: Create directory structure**

```bash
mkdir -p tests/integration/mock_grist
```

**Step 2: Create requirements.txt**

Create `tests/integration/mock_grist/requirements.txt`:

```
starlette>=0.41.0
uvicorn>=0.32.0
```

**Step 3: Create __init__.py**

Create empty `tests/integration/mock_grist/__init__.py`:

```python
```

**Step 4: Create server.py**

Create `tests/integration/mock_grist/server.py`:

```python
"""Mock Grist API server for integration testing."""

import json
import logging
import os
from datetime import datetime

from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route

logging.basicConfig(level=logging.INFO, format="%(asctime)s [MOCK-GRIST] %(message)s")
logger = logging.getLogger(__name__)

# Mock data
MOCK_TABLES = {
    "People": {
        "columns": [
            {"id": "Name", "fields": {"type": "Text"}},
            {"id": "Age", "fields": {"type": "Int"}},
            {"id": "Email", "fields": {"type": "Text"}},
        ],
        "records": [
            {"id": 1, "fields": {"Name": "Alice", "Age": 30, "Email": "alice@example.com"}},
            {"id": 2, "fields": {"Name": "Bob", "Age": 25, "Email": "bob@example.com"}},
        ],
    },
    "Tasks": {
        "columns": [
            {"id": "Title", "fields": {"type": "Text"}},
            {"id": "Done", "fields": {"type": "Bool"}},
        ],
        "records": [
            {"id": 1, "fields": {"Title": "Write tests", "Done": False}},
            {"id": 2, "fields": {"Title": "Deploy", "Done": False}},
        ],
    },
}

# Track requests for test assertions
request_log: list[dict] = []


def log_request(method: str, path: str, body: dict | None = None):
    """Log a request for later inspection."""
    entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "method": method,
        "path": path,
        "body": body,
    }
    request_log.append(entry)
    logger.info(f"{method} {path}" + (f" body={json.dumps(body)}" if body else ""))


async def health(request):
    """Health check endpoint."""
    return JSONResponse({"status": "ok"})


async def get_request_log(request):
    """Return the request log for test assertions."""
    return JSONResponse(request_log)


async def clear_request_log(request):
    """Clear the request log."""
    request_log.clear()
    return JSONResponse({"status": "cleared"})


async def list_tables(request):
    """GET /api/docs/{doc_id}/tables"""
    doc_id = request.path_params["doc_id"]
    log_request("GET", f"/api/docs/{doc_id}/tables")
    tables = [{"id": name} for name in MOCK_TABLES.keys()]
    return JSONResponse({"tables": tables})


async def get_table_columns(request):
    """GET /api/docs/{doc_id}/tables/{table_id}/columns"""
    doc_id = request.path_params["doc_id"]
    table_id = request.path_params["table_id"]
    log_request("GET", f"/api/docs/{doc_id}/tables/{table_id}/columns")

    if table_id not in MOCK_TABLES:
        return JSONResponse({"error": "Table not found"}, status_code=404)

    return JSONResponse({"columns": MOCK_TABLES[table_id]["columns"]})


async def get_records(request):
    """GET /api/docs/{doc_id}/tables/{table_id}/records"""
    doc_id = request.path_params["doc_id"]
    table_id = request.path_params["table_id"]
    log_request("GET", f"/api/docs/{doc_id}/tables/{table_id}/records")

    if table_id not in MOCK_TABLES:
        return JSONResponse({"error": "Table not found"}, status_code=404)

    return JSONResponse({"records": MOCK_TABLES[table_id]["records"]})


async def add_records(request):
    """POST /api/docs/{doc_id}/tables/{table_id}/records"""
    doc_id = request.path_params["doc_id"]
    table_id = request.path_params["table_id"]
    body = await request.json()
    log_request("POST", f"/api/docs/{doc_id}/tables/{table_id}/records", body)

    # Return mock IDs for new records
    new_ids = [{"id": 100 + i} for i in range(len(body.get("records", [])))]
    return JSONResponse({"records": new_ids})


async def update_records(request):
    """PATCH /api/docs/{doc_id}/tables/{table_id}/records"""
    doc_id = request.path_params["doc_id"]
    table_id = request.path_params["table_id"]
    body = await request.json()
    log_request("PATCH", f"/api/docs/{doc_id}/tables/{table_id}/records", body)
    return JSONResponse({})


async def delete_records(request):
    """POST /api/docs/{doc_id}/tables/{table_id}/data/delete"""
    doc_id = request.path_params["doc_id"]
    table_id = request.path_params["table_id"]
    body = await request.json()
    log_request("POST", f"/api/docs/{doc_id}/tables/{table_id}/data/delete", body)
    return JSONResponse({})


async def sql_query(request):
    """GET /api/docs/{doc_id}/sql"""
    doc_id = request.path_params["doc_id"]
    query = request.query_params.get("q", "")
    log_request("GET", f"/api/docs/{doc_id}/sql?q={query}")

    # Return mock SQL results
    return JSONResponse({
        "records": [
            {"fields": {"Name": "Alice", "Age": 30}},
            {"fields": {"Name": "Bob", "Age": 25}},
        ]
    })


async def create_tables(request):
    """POST /api/docs/{doc_id}/tables"""
    doc_id = request.path_params["doc_id"]
    body = await request.json()
    log_request("POST", f"/api/docs/{doc_id}/tables", body)

    # Return the created tables with their IDs
    tables = [{"id": t["id"]} for t in body.get("tables", [])]
    return JSONResponse({"tables": tables})


async def add_column(request):
    """POST /api/docs/{doc_id}/tables/{table_id}/columns"""
    doc_id = request.path_params["doc_id"]
    table_id = request.path_params["table_id"]
    body = await request.json()
    log_request("POST", f"/api/docs/{doc_id}/tables/{table_id}/columns", body)

    columns = [{"id": c["id"]} for c in body.get("columns", [])]
    return JSONResponse({"columns": columns})


async def modify_column(request):
    """PATCH /api/docs/{doc_id}/tables/{table_id}/columns/{col_id}"""
    doc_id = request.path_params["doc_id"]
    table_id = request.path_params["table_id"]
    col_id = request.path_params["col_id"]
    body = await request.json()
    log_request("PATCH", f"/api/docs/{doc_id}/tables/{table_id}/columns/{col_id}", body)
    return JSONResponse({})


async def delete_column(request):
    """DELETE /api/docs/{doc_id}/tables/{table_id}/columns/{col_id}"""
    doc_id = request.path_params["doc_id"]
    table_id = request.path_params["table_id"]
    col_id = request.path_params["col_id"]
    log_request("DELETE", f"/api/docs/{doc_id}/tables/{table_id}/columns/{col_id}")
    return JSONResponse({})


app = Starlette(
    routes=[
        # Test control endpoints
        Route("/health", endpoint=health),
        Route("/_test/requests", endpoint=get_request_log),
        Route("/_test/requests/clear", endpoint=clear_request_log, methods=["POST"]),

        # Grist API endpoints
        Route("/api/docs/{doc_id}/tables", endpoint=list_tables),
        Route("/api/docs/{doc_id}/tables", endpoint=create_tables, methods=["POST"]),
        Route("/api/docs/{doc_id}/tables/{table_id}/columns", endpoint=get_table_columns),
        Route("/api/docs/{doc_id}/tables/{table_id}/columns", endpoint=add_column, methods=["POST"]),
        Route("/api/docs/{doc_id}/tables/{table_id}/columns/{col_id}", endpoint=modify_column, methods=["PATCH"]),
        Route("/api/docs/{doc_id}/tables/{table_id}/columns/{col_id}", endpoint=delete_column, methods=["DELETE"]),
        Route("/api/docs/{doc_id}/tables/{table_id}/records", endpoint=get_records),
        Route("/api/docs/{doc_id}/tables/{table_id}/records", endpoint=add_records, methods=["POST"]),
        Route("/api/docs/{doc_id}/tables/{table_id}/records", endpoint=update_records, methods=["PATCH"]),
        Route("/api/docs/{doc_id}/tables/{table_id}/data/delete", endpoint=delete_records, methods=["POST"]),
        Route("/api/docs/{doc_id}/sql", endpoint=sql_query),
    ]
)


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", "8484"))
    logger.info(f"Starting mock Grist server on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)
```

**Step 5: Create Dockerfile**

Create `tests/integration/mock_grist/Dockerfile`:

```dockerfile
FROM python:3.14-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY server.py .

ENV PORT=8484
EXPOSE 8484

CMD ["python", "server.py"]
```

**Step 6: Commit**

```bash
git add tests/integration/mock_grist/
git commit -m "feat: add mock Grist server for integration testing"
```

---

## Task 3: Create Integration Test Configuration

**Files:**
- Create: `tests/integration/__init__.py`
- Create: `tests/integration/config.test.yaml`

**Step 1: Create __init__.py**

Create empty `tests/integration/__init__.py`:

```python
```

**Step 2: Create config.test.yaml**

Create `tests/integration/config.test.yaml`:

```yaml
documents:
  test-doc:
    url: http://mock-grist:8484
    doc_id: test-doc-id
    api_key: test-api-key

tokens:
  - token: test-token
    name: test-agent
    scope:
      - document: test-doc
        permissions: [read, write, schema]
```

**Step 3: Commit**

```bash
git add tests/integration/__init__.py tests/integration/config.test.yaml
git commit -m "feat: add integration test configuration"
```

---

## Task 4: Create Docker Compose Test Configuration

**Files:**
- Create: `docker-compose.test.yaml`

**Step 1: Create docker-compose.test.yaml**

Create `docker-compose.test.yaml`:

```yaml
services:
  grist-mcp:
    build: .
    ports:
      - "3000:3000"
    environment:
      - CONFIG_PATH=/app/config.yaml
      - GRIST_MCP_TOKEN=test-token
      - PORT=3000
    volumes:
      - ./tests/integration/config.test.yaml:/app/config.yaml:ro
    depends_on:
      mock-grist:
        condition: service_started
    networks:
      - test-net
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:3000/health')"]
      interval: 5s
      timeout: 5s
      retries: 5

  mock-grist:
    build: tests/integration/mock_grist
    ports:
      - "8484:8484"
    environment:
      - PORT=8484
    networks:
      - test-net
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8484/health')"]
      interval: 5s
      timeout: 5s
      retries: 5

networks:
  test-net:
    driver: bridge
```

**Step 2: Commit**

```bash
git add docker-compose.test.yaml
git commit -m "feat: add docker-compose for integration testing"
```

---

## Task 5: Create Integration Test Fixtures

**Files:**
- Create: `tests/integration/conftest.py`

**Step 1: Create conftest.py**

Create `tests/integration/conftest.py`:

```python
"""Fixtures for integration tests."""

import asyncio
import time

import httpx
import pytest
from mcp import ClientSession
from mcp.client.sse import sse_client


GRIST_MCP_URL = "http://localhost:3000"
MOCK_GRIST_URL = "http://localhost:8484"
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


@pytest.fixture
async def mcp_client(services_ready):
    """Create an MCP client connected to grist-mcp via SSE."""
    async with sse_client(f"{GRIST_MCP_URL}/sse") as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            yield session


@pytest.fixture
def mock_grist_client(services_ready):
    """HTTP client for interacting with mock Grist test endpoints."""
    with httpx.Client(base_url=MOCK_GRIST_URL, timeout=10.0) as client:
        yield client


@pytest.fixture(autouse=True)
def clear_mock_grist_log(mock_grist_client):
    """Clear the mock Grist request log before each test."""
    mock_grist_client.post("/_test/requests/clear")
    yield
```

**Step 2: Commit**

```bash
git add tests/integration/conftest.py
git commit -m "feat: add integration test fixtures with MCP client"
```

---

## Task 6: Create MCP Protocol Tests

**Files:**
- Create: `tests/integration/test_mcp_protocol.py`

**Step 1: Create test_mcp_protocol.py**

Create `tests/integration/test_mcp_protocol.py`:

```python
"""Test MCP protocol compliance over SSE transport."""

import pytest


@pytest.mark.asyncio
async def test_mcp_connection_initializes(mcp_client):
    """Test that MCP client can connect and initialize."""
    # If we get here, connection and initialization succeeded
    assert mcp_client is not None


@pytest.mark.asyncio
async def test_list_tools_returns_all_tools(mcp_client):
    """Test that list_tools returns all expected tools."""
    result = await mcp_client.list_tools()
    tool_names = [tool.name for tool in result.tools]

    expected_tools = [
        "list_documents",
        "list_tables",
        "describe_table",
        "get_records",
        "sql_query",
        "add_records",
        "update_records",
        "delete_records",
        "create_table",
        "add_column",
        "modify_column",
        "delete_column",
    ]

    for expected in expected_tools:
        assert expected in tool_names, f"Missing tool: {expected}"

    assert len(result.tools) == 12


@pytest.mark.asyncio
async def test_list_tools_has_descriptions(mcp_client):
    """Test that all tools have descriptions."""
    result = await mcp_client.list_tools()

    for tool in result.tools:
        assert tool.description, f"Tool {tool.name} has no description"
        assert len(tool.description) > 10, f"Tool {tool.name} description too short"


@pytest.mark.asyncio
async def test_list_tools_has_input_schemas(mcp_client):
    """Test that all tools have input schemas."""
    result = await mcp_client.list_tools()

    for tool in result.tools:
        assert tool.inputSchema is not None, f"Tool {tool.name} has no inputSchema"
        assert "type" in tool.inputSchema, f"Tool {tool.name} schema missing type"
```

**Step 2: Commit**

```bash
git add tests/integration/test_mcp_protocol.py
git commit -m "feat: add MCP protocol compliance tests"
```

---

## Task 7: Create Tool Integration Tests

**Files:**
- Create: `tests/integration/test_tools_integration.py`

**Step 1: Create test_tools_integration.py**

Create `tests/integration/test_tools_integration.py`:

```python
"""Test tool calls through MCP client to verify Grist API interactions."""

import json

import pytest


@pytest.mark.asyncio
async def test_list_documents(mcp_client):
    """Test list_documents returns accessible documents."""
    result = await mcp_client.call_tool("list_documents", {})

    assert len(result.content) == 1
    data = json.loads(result.content[0].text)

    assert "documents" in data
    assert len(data["documents"]) == 1
    assert data["documents"][0]["name"] == "test-doc"
    assert "read" in data["documents"][0]["permissions"]


@pytest.mark.asyncio
async def test_list_tables(mcp_client, mock_grist_client):
    """Test list_tables calls correct Grist API endpoint."""
    result = await mcp_client.call_tool("list_tables", {"document": "test-doc"})

    # Check response
    data = json.loads(result.content[0].text)
    assert "tables" in data
    assert "People" in data["tables"]
    assert "Tasks" in data["tables"]

    # Verify mock received correct request
    log = mock_grist_client.get("/_test/requests").json()
    assert len(log) >= 1
    assert log[-1]["method"] == "GET"
    assert "/tables" in log[-1]["path"]


@pytest.mark.asyncio
async def test_describe_table(mcp_client, mock_grist_client):
    """Test describe_table returns column information."""
    result = await mcp_client.call_tool(
        "describe_table",
        {"document": "test-doc", "table": "People"}
    )

    data = json.loads(result.content[0].text)
    assert "columns" in data

    column_ids = [c["id"] for c in data["columns"]]
    assert "Name" in column_ids
    assert "Age" in column_ids

    # Verify API call
    log = mock_grist_client.get("/_test/requests").json()
    assert any("/columns" in entry["path"] for entry in log)


@pytest.mark.asyncio
async def test_get_records(mcp_client, mock_grist_client):
    """Test get_records fetches records from table."""
    result = await mcp_client.call_tool(
        "get_records",
        {"document": "test-doc", "table": "People"}
    )

    data = json.loads(result.content[0].text)
    assert "records" in data
    assert len(data["records"]) == 2
    assert data["records"][0]["Name"] == "Alice"

    # Verify API call
    log = mock_grist_client.get("/_test/requests").json()
    assert any("/records" in entry["path"] and entry["method"] == "GET" for entry in log)


@pytest.mark.asyncio
async def test_sql_query(mcp_client, mock_grist_client):
    """Test sql_query executes SQL and returns results."""
    result = await mcp_client.call_tool(
        "sql_query",
        {"document": "test-doc", "query": "SELECT Name, Age FROM People"}
    )

    data = json.loads(result.content[0].text)
    assert "records" in data
    assert len(data["records"]) >= 1

    # Verify API call
    log = mock_grist_client.get("/_test/requests").json()
    assert any("/sql" in entry["path"] for entry in log)


@pytest.mark.asyncio
async def test_add_records(mcp_client, mock_grist_client):
    """Test add_records sends correct payload to Grist."""
    new_records = [
        {"Name": "Charlie", "Age": 35, "Email": "charlie@example.com"}
    ]

    result = await mcp_client.call_tool(
        "add_records",
        {"document": "test-doc", "table": "People", "records": new_records}
    )

    data = json.loads(result.content[0].text)
    assert "record_ids" in data
    assert len(data["record_ids"]) == 1

    # Verify API call body
    log = mock_grist_client.get("/_test/requests").json()
    post_requests = [e for e in log if e["method"] == "POST" and "/records" in e["path"]]
    assert len(post_requests) >= 1
    assert post_requests[-1]["body"]["records"][0]["fields"]["Name"] == "Charlie"


@pytest.mark.asyncio
async def test_update_records(mcp_client, mock_grist_client):
    """Test update_records sends correct payload to Grist."""
    updates = [
        {"id": 1, "fields": {"Age": 31}}
    ]

    result = await mcp_client.call_tool(
        "update_records",
        {"document": "test-doc", "table": "People", "records": updates}
    )

    data = json.loads(result.content[0].text)
    assert "updated" in data

    # Verify API call
    log = mock_grist_client.get("/_test/requests").json()
    patch_requests = [e for e in log if e["method"] == "PATCH" and "/records" in e["path"]]
    assert len(patch_requests) >= 1


@pytest.mark.asyncio
async def test_delete_records(mcp_client, mock_grist_client):
    """Test delete_records sends correct IDs to Grist."""
    result = await mcp_client.call_tool(
        "delete_records",
        {"document": "test-doc", "table": "People", "record_ids": [1, 2]}
    )

    data = json.loads(result.content[0].text)
    assert "deleted" in data

    # Verify API call
    log = mock_grist_client.get("/_test/requests").json()
    delete_requests = [e for e in log if "/data/delete" in e["path"]]
    assert len(delete_requests) >= 1
    assert delete_requests[-1]["body"] == [1, 2]


@pytest.mark.asyncio
async def test_create_table(mcp_client, mock_grist_client):
    """Test create_table sends correct schema to Grist."""
    columns = [
        {"id": "Title", "type": "Text"},
        {"id": "Count", "type": "Int"},
    ]

    result = await mcp_client.call_tool(
        "create_table",
        {"document": "test-doc", "table_id": "NewTable", "columns": columns}
    )

    data = json.loads(result.content[0].text)
    assert "table_id" in data

    # Verify API call
    log = mock_grist_client.get("/_test/requests").json()
    post_tables = [e for e in log if e["method"] == "POST" and e["path"].endswith("/tables")]
    assert len(post_tables) >= 1


@pytest.mark.asyncio
async def test_add_column(mcp_client, mock_grist_client):
    """Test add_column sends correct column definition."""
    result = await mcp_client.call_tool(
        "add_column",
        {
            "document": "test-doc",
            "table": "People",
            "column_id": "Phone",
            "column_type": "Text",
        }
    )

    data = json.loads(result.content[0].text)
    assert "column_id" in data

    # Verify API call
    log = mock_grist_client.get("/_test/requests").json()
    post_cols = [e for e in log if e["method"] == "POST" and "/columns" in e["path"]]
    assert len(post_cols) >= 1


@pytest.mark.asyncio
async def test_modify_column(mcp_client, mock_grist_client):
    """Test modify_column sends correct update."""
    result = await mcp_client.call_tool(
        "modify_column",
        {
            "document": "test-doc",
            "table": "People",
            "column_id": "Age",
            "type": "Numeric",
        }
    )

    data = json.loads(result.content[0].text)
    assert "modified" in data

    # Verify API call
    log = mock_grist_client.get("/_test/requests").json()
    patch_cols = [e for e in log if e["method"] == "PATCH" and "/columns/" in e["path"]]
    assert len(patch_cols) >= 1


@pytest.mark.asyncio
async def test_delete_column(mcp_client, mock_grist_client):
    """Test delete_column calls correct endpoint."""
    result = await mcp_client.call_tool(
        "delete_column",
        {
            "document": "test-doc",
            "table": "People",
            "column_id": "Email",
        }
    )

    data = json.loads(result.content[0].text)
    assert "deleted" in data

    # Verify API call
    log = mock_grist_client.get("/_test/requests").json()
    delete_cols = [e for e in log if e["method"] == "DELETE" and "/columns/" in e["path"]]
    assert len(delete_cols) >= 1


@pytest.mark.asyncio
async def test_unauthorized_document_fails(mcp_client):
    """Test that accessing unauthorized document returns error."""
    result = await mcp_client.call_tool(
        "list_tables",
        {"document": "unauthorized-doc"}
    )

    assert "error" in result.content[0].text.lower() or "authorization" in result.content[0].text.lower()
```

**Step 2: Commit**

```bash
git add tests/integration/test_tools_integration.py
git commit -m "feat: add tool integration tests with Grist API validation"
```

---

## Task 8: Create Makefile

**Files:**
- Create: `Makefile`

**Step 1: Create Makefile**

Create `Makefile`:

```makefile
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
```

**Step 2: Verify Makefile syntax**

Run: `make help`
Expected: List of available targets with descriptions

**Step 3: Commit**

```bash
git add Makefile
git commit -m "feat: add Makefile for test orchestration"
```

---

## Task 9: Run Full Pre-Deploy Pipeline

**Step 1: Run unit tests**

Run: `make test`
Expected: All unit tests pass

**Step 2: Run full pre-deploy**

Run: `make pre-deploy`
Expected: Unit tests pass, Docker builds succeed, integration tests pass, containers cleaned up

**Step 3: Commit any fixes needed**

If any tests fail, fix them and commit:

```bash
git add -A
git commit -m "fix: resolve integration test issues"
```

---

## Summary

Files created:
- `src/grist_mcp/main.py` - Modified with /health endpoint
- `tests/integration/mock_grist/__init__.py`
- `tests/integration/mock_grist/server.py`
- `tests/integration/mock_grist/Dockerfile`
- `tests/integration/mock_grist/requirements.txt`
- `tests/integration/__init__.py`
- `tests/integration/config.test.yaml`
- `tests/integration/conftest.py`
- `tests/integration/test_mcp_protocol.py`
- `tests/integration/test_tools_integration.py`
- `docker-compose.test.yaml`
- `Makefile`

Usage:
```bash
make help        # Show all targets
make test        # Unit tests only
make integration # Integration tests only
make pre-deploy  # Full pipeline
make clean       # Cleanup
```
