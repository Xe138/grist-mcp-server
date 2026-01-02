# Session Token Proxy Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Enable agents to delegate bulk data operations to scripts via short-lived session tokens and an HTTP proxy endpoint.

**Architecture:** Add `SessionTokenManager` for in-memory token storage, `get_proxy_documentation` and `request_session_token` MCP tools, and a `POST /api/v1/proxy` HTTP endpoint that validates session tokens and dispatches to existing tool functions.

**Tech Stack:** Python 3.14+, MCP SDK, httpx, pytest + pytest-asyncio

---

## Task 1: SessionTokenManager - Token Creation

**Files:**
- Create: `src/grist_mcp/session.py`
- Create: `tests/unit/test_session.py`

**Step 1: Write the failing test for token creation**

Create `tests/unit/test_session.py`:

```python
import pytest
from datetime import datetime, timedelta, timezone

from grist_mcp.session import SessionTokenManager, SessionToken


def test_create_token_returns_valid_session_token():
    manager = SessionTokenManager()

    token = manager.create_token(
        agent_name="test-agent",
        document="sales",
        permissions=["read", "write"],
        ttl_seconds=300,
    )

    assert token.token.startswith("sess_")
    assert len(token.token) > 20
    assert token.document == "sales"
    assert token.permissions == ["read", "write"]
    assert token.agent_name == "test-agent"
    assert token.expires_at > datetime.now(timezone.utc)
    assert token.expires_at < datetime.now(timezone.utc) + timedelta(seconds=310)
```

**Step 2: Run test to verify it fails**

Run: `cd /home/bballou/grist-mcp/.worktrees/session-proxy && uv run pytest tests/unit/test_session.py::test_create_token_returns_valid_session_token -v`

Expected: FAIL with "No module named 'grist_mcp.session'"

**Step 3: Write minimal implementation**

Create `src/grist_mcp/session.py`:

```python
"""Session token management for HTTP proxy access."""

import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone


@dataclass
class SessionToken:
    """A short-lived session token for proxy access."""
    token: str
    document: str
    permissions: list[str]
    agent_name: str
    created_at: datetime
    expires_at: datetime


class SessionTokenManager:
    """Manages creation and validation of session tokens."""

    def __init__(self):
        self._tokens: dict[str, SessionToken] = {}

    def create_token(
        self,
        agent_name: str,
        document: str,
        permissions: list[str],
        ttl_seconds: int,
    ) -> SessionToken:
        """Create a new session token."""
        now = datetime.now(timezone.utc)
        token_str = f"sess_{secrets.token_urlsafe(32)}"

        session = SessionToken(
            token=token_str,
            document=document,
            permissions=permissions,
            agent_name=agent_name,
            created_at=now,
            expires_at=now + timedelta(seconds=ttl_seconds),
        )

        self._tokens[token_str] = session
        return session
```

**Step 4: Run test to verify it passes**

Run: `cd /home/bballou/grist-mcp/.worktrees/session-proxy && uv run pytest tests/unit/test_session.py::test_create_token_returns_valid_session_token -v`

Expected: PASS

**Step 5: Commit**

```bash
cd /home/bballou/grist-mcp/.worktrees/session-proxy
git add src/grist_mcp/session.py tests/unit/test_session.py
git commit -m "feat(session): add SessionTokenManager with token creation"
```

---

## Task 2: SessionTokenManager - TTL Capping

**Files:**
- Modify: `src/grist_mcp/session.py`
- Modify: `tests/unit/test_session.py`

**Step 1: Write the failing test for TTL capping**

Add to `tests/unit/test_session.py`:

```python
def test_create_token_caps_ttl_at_maximum():
    manager = SessionTokenManager()

    # Request 2 hours, should be capped at 1 hour
    token = manager.create_token(
        agent_name="test-agent",
        document="sales",
        permissions=["read"],
        ttl_seconds=7200,
    )

    # Should be capped at 3600 seconds (1 hour)
    max_expires = datetime.now(timezone.utc) + timedelta(seconds=3610)
    assert token.expires_at < max_expires
```

**Step 2: Run test to verify it fails**

Run: `cd /home/bballou/grist-mcp/.worktrees/session-proxy && uv run pytest tests/unit/test_session.py::test_create_token_caps_ttl_at_maximum -v`

Expected: FAIL (token expires_at will be ~2 hours, not capped)

**Step 3: Update implementation to cap TTL**

In `src/grist_mcp/session.py`, update `create_token`:

```python
MAX_TTL_SECONDS = 3600  # 1 hour
DEFAULT_TTL_SECONDS = 300  # 5 minutes
```

Add at module level, then modify `create_token`:

```python
    def create_token(
        self,
        agent_name: str,
        document: str,
        permissions: list[str],
        ttl_seconds: int = DEFAULT_TTL_SECONDS,
    ) -> SessionToken:
        """Create a new session token.

        TTL is capped at MAX_TTL_SECONDS (1 hour).
        """
        now = datetime.now(timezone.utc)
        token_str = f"sess_{secrets.token_urlsafe(32)}"

        # Cap TTL at maximum
        effective_ttl = min(ttl_seconds, MAX_TTL_SECONDS)

        session = SessionToken(
            token=token_str,
            document=document,
            permissions=permissions,
            agent_name=agent_name,
            created_at=now,
            expires_at=now + timedelta(seconds=effective_ttl),
        )

        self._tokens[token_str] = session
        return session
```

**Step 4: Run test to verify it passes**

Run: `cd /home/bballou/grist-mcp/.worktrees/session-proxy && uv run pytest tests/unit/test_session.py -v`

Expected: PASS (both tests)

**Step 5: Commit**

```bash
cd /home/bballou/grist-mcp/.worktrees/session-proxy
git add src/grist_mcp/session.py tests/unit/test_session.py
git commit -m "feat(session): cap TTL at 1 hour maximum"
```

---

## Task 3: SessionTokenManager - Token Validation

**Files:**
- Modify: `src/grist_mcp/session.py`
- Modify: `tests/unit/test_session.py`

**Step 1: Write the failing test for valid token**

Add to `tests/unit/test_session.py`:

```python
def test_validate_token_returns_session_for_valid_token():
    manager = SessionTokenManager()
    created = manager.create_token(
        agent_name="test-agent",
        document="sales",
        permissions=["read"],
        ttl_seconds=300,
    )

    session = manager.validate_token(created.token)

    assert session is not None
    assert session.document == "sales"
    assert session.agent_name == "test-agent"
```

**Step 2: Run test to verify it fails**

Run: `cd /home/bballou/grist-mcp/.worktrees/session-proxy && uv run pytest tests/unit/test_session.py::test_validate_token_returns_session_for_valid_token -v`

Expected: FAIL with "SessionTokenManager has no attribute 'validate_token'"

**Step 3: Write minimal implementation**

Add to `SessionTokenManager` class in `src/grist_mcp/session.py`:

```python
    def validate_token(self, token: str) -> SessionToken | None:
        """Validate a session token.

        Returns the SessionToken if valid and not expired, None otherwise.
        Also removes expired tokens lazily.
        """
        session = self._tokens.get(token)
        if session is None:
            return None

        now = datetime.now(timezone.utc)
        if session.expires_at < now:
            # Token expired, remove it
            del self._tokens[token]
            return None

        return session
```

**Step 4: Run test to verify it passes**

Run: `cd /home/bballou/grist-mcp/.worktrees/session-proxy && uv run pytest tests/unit/test_session.py -v`

Expected: PASS (all tests)

**Step 5: Commit**

```bash
cd /home/bballou/grist-mcp/.worktrees/session-proxy
git add src/grist_mcp/session.py tests/unit/test_session.py
git commit -m "feat(session): add token validation"
```

---

## Task 4: SessionTokenManager - Invalid and Expired Token Handling

**Files:**
- Modify: `tests/unit/test_session.py`

**Step 1: Write failing tests for invalid and expired tokens**

Add to `tests/unit/test_session.py`:

```python
def test_validate_token_returns_none_for_unknown_token():
    manager = SessionTokenManager()

    session = manager.validate_token("sess_unknown_token")

    assert session is None


def test_validate_token_returns_none_for_expired_token():
    manager = SessionTokenManager()
    created = manager.create_token(
        agent_name="test-agent",
        document="sales",
        permissions=["read"],
        ttl_seconds=1,
    )

    # Wait for expiry (we'll use time manipulation instead)
    import time
    time.sleep(1.1)

    session = manager.validate_token(created.token)

    assert session is None
```

**Step 2: Run tests to verify they pass**

Run: `cd /home/bballou/grist-mcp/.worktrees/session-proxy && uv run pytest tests/unit/test_session.py -v`

Expected: PASS (implementation already handles these cases)

**Step 3: Commit**

```bash
cd /home/bballou/grist-mcp/.worktrees/session-proxy
git add tests/unit/test_session.py
git commit -m "test(session): add tests for invalid and expired tokens"
```

---

## Task 5: get_proxy_documentation MCP Tool

**Files:**
- Create: `src/grist_mcp/tools/session.py`
- Create: `tests/unit/test_tools_session.py`
- Modify: `src/grist_mcp/server.py`

**Step 1: Write the failing test for documentation tool**

Create `tests/unit/test_tools_session.py`:

```python
import pytest
from grist_mcp.tools.session import get_proxy_documentation


@pytest.mark.asyncio
async def test_get_proxy_documentation_returns_complete_spec():
    result = await get_proxy_documentation()

    assert "description" in result
    assert "endpoint" in result
    assert result["endpoint"] == "POST /api/v1/proxy"
    assert "authentication" in result
    assert "methods" in result
    assert "add_records" in result["methods"]
    assert "get_records" in result["methods"]
    assert "example_script" in result
```

**Step 2: Run test to verify it fails**

Run: `cd /home/bballou/grist-mcp/.worktrees/session-proxy && uv run pytest tests/unit/test_tools_session.py::test_get_proxy_documentation_returns_complete_spec -v`

Expected: FAIL with "No module named 'grist_mcp.tools.session'"

**Step 3: Write the implementation**

Create `src/grist_mcp/tools/session.py`:

```python
"""Session token tools for HTTP proxy access."""

from grist_mcp.auth import Agent, Authenticator, AuthError
from grist_mcp.session import SessionTokenManager


PROXY_DOCUMENTATION = {
    "description": "HTTP proxy API for bulk data operations. Use request_session_token to get a short-lived token, then call the proxy endpoint directly from scripts.",
    "endpoint": "POST /api/v1/proxy",
    "authentication": "Bearer token in Authorization header",
    "request_format": {
        "method": "Operation name (required)",
        "table": "Table name (required for most operations)",
    },
    "methods": {
        "get_records": {
            "description": "Fetch records from a table",
            "fields": {
                "table": "string",
                "filter": "object (optional)",
                "sort": "string (optional)",
                "limit": "integer (optional)",
            },
        },
        "sql_query": {
            "description": "Run a read-only SQL query",
            "fields": {"query": "string"},
        },
        "list_tables": {
            "description": "List all tables in the document",
            "fields": {},
        },
        "describe_table": {
            "description": "Get column information for a table",
            "fields": {"table": "string"},
        },
        "add_records": {
            "description": "Add records to a table",
            "fields": {"table": "string", "records": "array of objects"},
        },
        "update_records": {
            "description": "Update existing records",
            "fields": {"table": "string", "records": "array of {id, fields}"},
        },
        "delete_records": {
            "description": "Delete records by ID",
            "fields": {"table": "string", "record_ids": "array of integers"},
        },
        "create_table": {
            "description": "Create a new table",
            "fields": {"table_id": "string", "columns": "array of {id, type}"},
        },
        "add_column": {
            "description": "Add a column to a table",
            "fields": {
                "table": "string",
                "column_id": "string",
                "column_type": "string",
                "formula": "string (optional)",
            },
        },
        "modify_column": {
            "description": "Modify a column's type or formula",
            "fields": {
                "table": "string",
                "column_id": "string",
                "type": "string (optional)",
                "formula": "string (optional)",
            },
        },
        "delete_column": {
            "description": "Delete a column",
            "fields": {"table": "string", "column_id": "string"},
        },
    },
    "response_format": {
        "success": {"success": True, "data": "..."},
        "error": {"success": False, "error": "message", "code": "ERROR_CODE"},
    },
    "error_codes": [
        "UNAUTHORIZED",
        "INVALID_TOKEN",
        "TOKEN_EXPIRED",
        "INVALID_REQUEST",
        "GRIST_ERROR",
    ],
    "example_script": """#!/usr/bin/env python3
import requests
import sys

token = sys.argv[1]
host = sys.argv[2]

response = requests.post(
    f'{host}/api/v1/proxy',
    headers={'Authorization': f'Bearer {token}'},
    json={
        'method': 'add_records',
        'table': 'Orders',
        'records': [{'item': 'Widget', 'qty': 100}]
    }
)
print(response.json())
""",
}


async def get_proxy_documentation() -> dict:
    """Return complete documentation for the HTTP proxy API."""
    return PROXY_DOCUMENTATION
```

**Step 4: Run test to verify it passes**

Run: `cd /home/bballou/grist-mcp/.worktrees/session-proxy && uv run pytest tests/unit/test_tools_session.py -v`

Expected: PASS

**Step 5: Commit**

```bash
cd /home/bballou/grist-mcp/.worktrees/session-proxy
git add src/grist_mcp/tools/session.py tests/unit/test_tools_session.py
git commit -m "feat(tools): add get_proxy_documentation tool"
```

---

## Task 6: request_session_token MCP Tool

**Files:**
- Modify: `src/grist_mcp/tools/session.py`
- Modify: `tests/unit/test_tools_session.py`

**Step 1: Write the failing test**

Add to `tests/unit/test_tools_session.py`:

```python
from grist_mcp.auth import Authenticator, Agent
from grist_mcp.config import Config, Document, Token, TokenScope
from grist_mcp.session import SessionTokenManager
from grist_mcp.tools.session import request_session_token


@pytest.fixture
def sample_config():
    return Config(
        documents={
            "sales": Document(
                url="https://grist.example.com",
                doc_id="abc123",
                api_key="key",
            ),
        },
        tokens=[
            Token(
                token="agent-token",
                name="test-agent",
                scope=[
                    TokenScope(document="sales", permissions=["read", "write"]),
                ],
            ),
        ],
    )


@pytest.fixture
def auth_and_agent(sample_config):
    auth = Authenticator(sample_config)
    agent = auth.authenticate("agent-token")
    return auth, agent


@pytest.mark.asyncio
async def test_request_session_token_creates_valid_token(auth_and_agent):
    auth, agent = auth_and_agent
    manager = SessionTokenManager()

    result = await request_session_token(
        agent=agent,
        auth=auth,
        token_manager=manager,
        document="sales",
        permissions=["read", "write"],
        ttl_seconds=300,
    )

    assert "token" in result
    assert result["token"].startswith("sess_")
    assert result["document"] == "sales"
    assert result["permissions"] == ["read", "write"]
    assert "expires_at" in result
    assert result["proxy_url"] == "/api/v1/proxy"
```

**Step 2: Run test to verify it fails**

Run: `cd /home/bballou/grist-mcp/.worktrees/session-proxy && uv run pytest tests/unit/test_tools_session.py::test_request_session_token_creates_valid_token -v`

Expected: FAIL with "cannot import name 'request_session_token'"

**Step 3: Write the implementation**

Add to `src/grist_mcp/tools/session.py`:

```python
async def request_session_token(
    agent: Agent,
    auth: Authenticator,
    token_manager: SessionTokenManager,
    document: str,
    permissions: list[str],
    ttl_seconds: int = 300,
) -> dict:
    """Request a short-lived session token for HTTP proxy access.

    The token can only grant permissions the agent already has.
    """
    # Verify agent has access to the document
    # Check each requested permission
    from grist_mcp.auth import Permission

    for perm_str in permissions:
        try:
            perm = Permission(perm_str)
        except ValueError:
            raise AuthError(f"Invalid permission: {perm_str}")
        auth.authorize(agent, document, perm)

    # Create the session token
    session = token_manager.create_token(
        agent_name=agent.name,
        document=document,
        permissions=permissions,
        ttl_seconds=ttl_seconds,
    )

    return {
        "token": session.token,
        "document": session.document,
        "permissions": session.permissions,
        "expires_at": session.expires_at.isoformat(),
        "proxy_url": "/api/v1/proxy",
    }
```

**Step 4: Run test to verify it passes**

Run: `cd /home/bballou/grist-mcp/.worktrees/session-proxy && uv run pytest tests/unit/test_tools_session.py -v`

Expected: PASS

**Step 5: Commit**

```bash
cd /home/bballou/grist-mcp/.worktrees/session-proxy
git add src/grist_mcp/tools/session.py tests/unit/test_tools_session.py
git commit -m "feat(tools): add request_session_token tool"
```

---

## Task 7: request_session_token Permission Validation

**Files:**
- Modify: `tests/unit/test_tools_session.py`

**Step 1: Write tests for permission denial**

Add to `tests/unit/test_tools_session.py`:

```python
from grist_mcp.auth import AuthError


@pytest.mark.asyncio
async def test_request_session_token_denies_escalation(auth_and_agent):
    auth, agent = auth_and_agent
    manager = SessionTokenManager()

    # Agent only has read/write on sales, not schema
    with pytest.raises(AuthError, match="Permission denied"):
        await request_session_token(
            agent=agent,
            auth=auth,
            token_manager=manager,
            document="sales",
            permissions=["schema"],
            ttl_seconds=300,
        )


@pytest.mark.asyncio
async def test_request_session_token_denies_unknown_document(auth_and_agent):
    auth, agent = auth_and_agent
    manager = SessionTokenManager()

    with pytest.raises(AuthError, match="Document not in scope"):
        await request_session_token(
            agent=agent,
            auth=auth,
            token_manager=manager,
            document="unknown",
            permissions=["read"],
            ttl_seconds=300,
        )
```

**Step 2: Run tests to verify they pass**

Run: `cd /home/bballou/grist-mcp/.worktrees/session-proxy && uv run pytest tests/unit/test_tools_session.py -v`

Expected: PASS (implementation already handles these via auth.authorize)

**Step 3: Commit**

```bash
cd /home/bballou/grist-mcp/.worktrees/session-proxy
git add tests/unit/test_tools_session.py
git commit -m "test(tools): add permission validation tests for session token"
```

---

## Task 8: Register Session Tools in Server

**Files:**
- Modify: `src/grist_mcp/server.py`
- Modify: `tests/unit/test_server.py`

**Step 1: Write failing test for tool registration**

Add to `tests/unit/test_server.py`:

```python
@pytest.mark.asyncio
async def test_create_server_registers_session_tools(sample_config):
    from grist_mcp.session import SessionTokenManager

    auth = Authenticator(sample_config)
    agent = auth.authenticate("valid-token")
    token_manager = SessionTokenManager()
    server = create_server(auth, agent, token_manager)

    tools = await server.list_tools()
    tool_names = [t.name for t in tools]

    assert "get_proxy_documentation" in tool_names
    assert "request_session_token" in tool_names
```

**Step 2: Run test to verify it fails**

Run: `cd /home/bballou/grist-mcp/.worktrees/session-proxy && uv run pytest tests/unit/test_server.py::test_create_server_registers_session_tools -v`

Expected: FAIL (create_server doesn't accept token_manager yet)

**Step 3: Update server.py to accept token_manager and register tools**

Modify `src/grist_mcp/server.py`:

1. Add import at top:
```python
from grist_mcp.session import SessionTokenManager
from grist_mcp.tools.session import get_proxy_documentation as _get_proxy_documentation
from grist_mcp.tools.session import request_session_token as _request_session_token
```

2. Update function signature:
```python
def create_server(auth: Authenticator, agent: Agent, token_manager: SessionTokenManager | None = None) -> Server:
```

3. Add tools to list_tools():
```python
            Tool(
                name="get_proxy_documentation",
                description="Get complete documentation for the HTTP proxy API",
                inputSchema={"type": "object", "properties": {}, "required": []},
            ),
            Tool(
                name="request_session_token",
                description="Request a short-lived token for direct HTTP API access. Use this to delegate bulk data operations to scripts.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "document": {
                            "type": "string",
                            "description": "Document name to grant access to",
                        },
                        "permissions": {
                            "type": "array",
                            "items": {"type": "string", "enum": ["read", "write", "schema"]},
                            "description": "Permission levels to grant",
                        },
                        "ttl_seconds": {
                            "type": "integer",
                            "description": "Token lifetime in seconds (max 3600, default 300)",
                        },
                    },
                    "required": ["document", "permissions"],
                },
            ),
```

4. Add handlers to call_tool():
```python
            elif name == "get_proxy_documentation":
                result = await _get_proxy_documentation()
            elif name == "request_session_token":
                if token_manager is None:
                    return [TextContent(type="text", text="Session tokens not enabled")]
                result = await _request_session_token(
                    _current_agent, auth, token_manager,
                    arguments["document"],
                    arguments["permissions"],
                    ttl_seconds=arguments.get("ttl_seconds", 300),
                )
```

**Step 4: Run all server tests**

Run: `cd /home/bballou/grist-mcp/.worktrees/session-proxy && uv run pytest tests/unit/test_server.py -v`

Expected: PASS

**Step 5: Commit**

```bash
cd /home/bballou/grist-mcp/.worktrees/session-proxy
git add src/grist_mcp/server.py tests/unit/test_server.py
git commit -m "feat(server): register session token tools"
```

---

## Task 9: HTTP Proxy Handler - Request Parsing

**Files:**
- Create: `src/grist_mcp/proxy.py`
- Create: `tests/unit/test_proxy.py`

**Step 1: Write failing test for request parsing**

Create `tests/unit/test_proxy.py`:

```python
import pytest
from grist_mcp.proxy import parse_proxy_request, ProxyRequest, ProxyError


def test_parse_proxy_request_valid_add_records():
    body = {
        "method": "add_records",
        "table": "Orders",
        "records": [{"item": "Widget", "qty": 10}],
    }

    request = parse_proxy_request(body)

    assert request.method == "add_records"
    assert request.table == "Orders"
    assert request.records == [{"item": "Widget", "qty": 10}]


def test_parse_proxy_request_missing_method():
    body = {"table": "Orders"}

    with pytest.raises(ProxyError) as exc_info:
        parse_proxy_request(body)

    assert exc_info.value.code == "INVALID_REQUEST"
    assert "method" in str(exc_info.value)
```

**Step 2: Run test to verify it fails**

Run: `cd /home/bballou/grist-mcp/.worktrees/session-proxy && uv run pytest tests/unit/test_proxy.py -v`

Expected: FAIL with "No module named 'grist_mcp.proxy'"

**Step 3: Write the implementation**

Create `src/grist_mcp/proxy.py`:

```python
"""HTTP proxy handler for session token access."""

from dataclasses import dataclass, field
from typing import Any


class ProxyError(Exception):
    """Error during proxy request processing."""

    def __init__(self, message: str, code: str):
        self.message = message
        self.code = code
        super().__init__(message)


@dataclass
class ProxyRequest:
    """Parsed proxy request."""
    method: str
    table: str | None = None
    records: list[dict] | None = None
    record_ids: list[int] | None = None
    filter: dict | None = None
    sort: str | None = None
    limit: int | None = None
    query: str | None = None
    table_id: str | None = None
    columns: list[dict] | None = None
    column_id: str | None = None
    column_type: str | None = None
    formula: str | None = None
    type: str | None = None


METHODS_REQUIRING_TABLE = {
    "get_records", "describe_table", "add_records", "update_records",
    "delete_records", "add_column", "modify_column", "delete_column",
}


def parse_proxy_request(body: dict[str, Any]) -> ProxyRequest:
    """Parse and validate a proxy request body."""
    if "method" not in body:
        raise ProxyError("Missing required field: method", "INVALID_REQUEST")

    method = body["method"]

    if method in METHODS_REQUIRING_TABLE and "table" not in body:
        raise ProxyError(f"Missing required field 'table' for method '{method}'", "INVALID_REQUEST")

    return ProxyRequest(
        method=method,
        table=body.get("table"),
        records=body.get("records"),
        record_ids=body.get("record_ids"),
        filter=body.get("filter"),
        sort=body.get("sort"),
        limit=body.get("limit"),
        query=body.get("query"),
        table_id=body.get("table_id"),
        columns=body.get("columns"),
        column_id=body.get("column_id"),
        column_type=body.get("column_type"),
        formula=body.get("formula"),
        type=body.get("type"),
    )
```

**Step 4: Run test to verify it passes**

Run: `cd /home/bballou/grist-mcp/.worktrees/session-proxy && uv run pytest tests/unit/test_proxy.py -v`

Expected: PASS

**Step 5: Commit**

```bash
cd /home/bballou/grist-mcp/.worktrees/session-proxy
git add src/grist_mcp/proxy.py tests/unit/test_proxy.py
git commit -m "feat(proxy): add request parsing"
```

---

## Task 10: HTTP Proxy Handler - Method Dispatch

**Files:**
- Modify: `src/grist_mcp/proxy.py`
- Modify: `tests/unit/test_proxy.py`

**Step 1: Write failing test for method dispatch**

Add to `tests/unit/test_proxy.py`:

```python
from unittest.mock import AsyncMock, MagicMock
from grist_mcp.proxy import dispatch_proxy_request
from grist_mcp.session import SessionToken
from datetime import datetime, timezone


@pytest.fixture
def mock_session():
    return SessionToken(
        token="sess_test",
        document="sales",
        permissions=["read", "write"],
        agent_name="test-agent",
        created_at=datetime.now(timezone.utc),
        expires_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def mock_auth():
    auth = MagicMock()
    doc = MagicMock()
    doc.url = "https://grist.example.com"
    doc.doc_id = "abc123"
    doc.api_key = "key"
    auth.get_document.return_value = doc
    return auth


@pytest.mark.asyncio
async def test_dispatch_add_records(mock_session, mock_auth):
    request = ProxyRequest(
        method="add_records",
        table="Orders",
        records=[{"item": "Widget"}],
    )

    mock_client = AsyncMock()
    mock_client.add_records.return_value = [1, 2, 3]

    result = await dispatch_proxy_request(
        request, mock_session, mock_auth, client=mock_client
    )

    assert result["success"] is True
    assert result["data"]["record_ids"] == [1, 2, 3]
    mock_client.add_records.assert_called_once_with("Orders", [{"item": "Widget"}])
```

**Step 2: Run test to verify it fails**

Run: `cd /home/bballou/grist-mcp/.worktrees/session-proxy && uv run pytest tests/unit/test_proxy.py::test_dispatch_add_records -v`

Expected: FAIL with "cannot import name 'dispatch_proxy_request'"

**Step 3: Write the implementation**

Add to `src/grist_mcp/proxy.py`:

```python
from grist_mcp.auth import Authenticator, Permission
from grist_mcp.session import SessionToken
from grist_mcp.grist_client import GristClient


# Map methods to required permissions
METHOD_PERMISSIONS = {
    "list_tables": "read",
    "describe_table": "read",
    "get_records": "read",
    "sql_query": "read",
    "add_records": "write",
    "update_records": "write",
    "delete_records": "write",
    "create_table": "schema",
    "add_column": "schema",
    "modify_column": "schema",
    "delete_column": "schema",
}


async def dispatch_proxy_request(
    request: ProxyRequest,
    session: SessionToken,
    auth: Authenticator,
    client: GristClient | None = None,
) -> dict[str, Any]:
    """Dispatch a proxy request to the appropriate handler."""
    # Check permission
    required_perm = METHOD_PERMISSIONS.get(request.method)
    if required_perm is None:
        raise ProxyError(f"Unknown method: {request.method}", "INVALID_REQUEST")

    if required_perm not in session.permissions:
        raise ProxyError(
            f"Permission '{required_perm}' required for {request.method}",
            "UNAUTHORIZED",
        )

    # Create client if not provided
    if client is None:
        doc = auth.get_document(session.document)
        client = GristClient(doc)

    # Dispatch to appropriate method
    try:
        if request.method == "list_tables":
            data = await client.list_tables()
            return {"success": True, "data": {"tables": data}}

        elif request.method == "describe_table":
            data = await client.describe_table(request.table)
            return {"success": True, "data": {"columns": data}}

        elif request.method == "get_records":
            data = await client.get_records(
                request.table,
                filter=request.filter,
                sort=request.sort,
                limit=request.limit,
            )
            return {"success": True, "data": {"records": data}}

        elif request.method == "sql_query":
            if request.query is None:
                raise ProxyError("Missing required field: query", "INVALID_REQUEST")
            data = await client.sql_query(request.query)
            return {"success": True, "data": data}

        elif request.method == "add_records":
            if request.records is None:
                raise ProxyError("Missing required field: records", "INVALID_REQUEST")
            data = await client.add_records(request.table, request.records)
            return {"success": True, "data": {"record_ids": data}}

        elif request.method == "update_records":
            if request.records is None:
                raise ProxyError("Missing required field: records", "INVALID_REQUEST")
            await client.update_records(request.table, request.records)
            return {"success": True, "data": {"updated": len(request.records)}}

        elif request.method == "delete_records":
            if request.record_ids is None:
                raise ProxyError("Missing required field: record_ids", "INVALID_REQUEST")
            await client.delete_records(request.table, request.record_ids)
            return {"success": True, "data": {"deleted": len(request.record_ids)}}

        elif request.method == "create_table":
            if request.table_id is None or request.columns is None:
                raise ProxyError("Missing required fields: table_id, columns", "INVALID_REQUEST")
            data = await client.create_table(request.table_id, request.columns)
            return {"success": True, "data": {"table_id": data}}

        elif request.method == "add_column":
            if request.column_id is None or request.column_type is None:
                raise ProxyError("Missing required fields: column_id, column_type", "INVALID_REQUEST")
            await client.add_column(
                request.table, request.column_id, request.column_type,
                formula=request.formula,
            )
            return {"success": True, "data": {"column_id": request.column_id}}

        elif request.method == "modify_column":
            if request.column_id is None:
                raise ProxyError("Missing required field: column_id", "INVALID_REQUEST")
            await client.modify_column(
                request.table, request.column_id,
                type=request.type,
                formula=request.formula,
            )
            return {"success": True, "data": {"column_id": request.column_id}}

        elif request.method == "delete_column":
            if request.column_id is None:
                raise ProxyError("Missing required field: column_id", "INVALID_REQUEST")
            await client.delete_column(request.table, request.column_id)
            return {"success": True, "data": {"deleted": request.column_id}}

        else:
            raise ProxyError(f"Unknown method: {request.method}", "INVALID_REQUEST")

    except ProxyError:
        raise
    except Exception as e:
        raise ProxyError(str(e), "GRIST_ERROR")
```

**Step 4: Run test to verify it passes**

Run: `cd /home/bballou/grist-mcp/.worktrees/session-proxy && uv run pytest tests/unit/test_proxy.py -v`

Expected: PASS

**Step 5: Commit**

```bash
cd /home/bballou/grist-mcp/.worktrees/session-proxy
git add src/grist_mcp/proxy.py tests/unit/test_proxy.py
git commit -m "feat(proxy): add method dispatch"
```

---

## Task 11: HTTP Proxy Handler - Permission Denial

**Files:**
- Modify: `tests/unit/test_proxy.py`

**Step 1: Write test for permission denial**

Add to `tests/unit/test_proxy.py`:

```python
@pytest.mark.asyncio
async def test_dispatch_denies_without_permission(mock_auth):
    # Session only has read permission
    session = SessionToken(
        token="sess_test",
        document="sales",
        permissions=["read"],  # No write
        agent_name="test-agent",
        created_at=datetime.now(timezone.utc),
        expires_at=datetime.now(timezone.utc),
    )

    request = ProxyRequest(
        method="add_records",  # Requires write
        table="Orders",
        records=[{"item": "Widget"}],
    )

    with pytest.raises(ProxyError) as exc_info:
        await dispatch_proxy_request(request, session, mock_auth)

    assert exc_info.value.code == "UNAUTHORIZED"
```

**Step 2: Run test to verify it passes**

Run: `cd /home/bballou/grist-mcp/.worktrees/session-proxy && uv run pytest tests/unit/test_proxy.py -v`

Expected: PASS (implementation already handles this)

**Step 3: Commit**

```bash
cd /home/bballou/grist-mcp/.worktrees/session-proxy
git add tests/unit/test_proxy.py
git commit -m "test(proxy): add permission denial test"
```

---

## Task 12: HTTP Proxy Endpoint in main.py

**Files:**
- Modify: `src/grist_mcp/main.py`

**Step 1: Add proxy imports and handler**

Add imports at top of `src/grist_mcp/main.py`:

```python
from grist_mcp.session import SessionTokenManager
from grist_mcp.proxy import parse_proxy_request, dispatch_proxy_request, ProxyError
```

**Step 2: Update create_app to create token manager**

In `create_app`, after `auth = Authenticator(config)`:

```python
    token_manager = SessionTokenManager()
```

**Step 3: Add proxy handler function**

Add inside `create_app`, after `handle_not_found`:

```python
    async def handle_proxy(scope: Scope, receive: Receive, send: Send) -> None:
        # Extract token
        token = _get_bearer_token(scope)
        if not token:
            await send_json_response(send, 401, {
                "success": False,
                "error": "Missing Authorization header",
                "code": "INVALID_TOKEN",
            })
            return

        # Validate session token
        session = token_manager.validate_token(token)
        if session is None:
            await send_json_response(send, 401, {
                "success": False,
                "error": "Invalid or expired token",
                "code": "TOKEN_EXPIRED",
            })
            return

        # Read request body
        body = b""
        while True:
            message = await receive()
            body += message.get("body", b"")
            if not message.get("more_body", False):
                break

        try:
            import json as json_mod
            request_data = json_mod.loads(body)
        except json_mod.JSONDecodeError:
            await send_json_response(send, 400, {
                "success": False,
                "error": "Invalid JSON",
                "code": "INVALID_REQUEST",
            })
            return

        # Parse and dispatch
        try:
            request = parse_proxy_request(request_data)
            result = await dispatch_proxy_request(request, session, auth)
            await send_json_response(send, 200, result)
        except ProxyError as e:
            status = 403 if e.code == "UNAUTHORIZED" else 400
            await send_json_response(send, status, {
                "success": False,
                "error": e.message,
                "code": e.code,
            })
```

**Step 4: Add helper for JSON responses**

Add after `send_error` function:

```python
async def send_json_response(send: Send, status: int, data: dict) -> None:
    """Send a JSON response."""
    body = json.dumps(data).encode()
    await send({
        "type": "http.response.start",
        "status": status,
        "headers": [[b"content-type", b"application/json"]],
    })
    await send({
        "type": "http.response.body",
        "body": body,
    })
```

**Step 5: Add route for /api/v1/proxy**

In the `app` function, add before the `else` clause:

```python
        elif path == "/api/v1/proxy" and method == "POST":
            await handle_proxy(scope, receive, send)
```

**Step 6: Update create_server call**

Change the `create_server` call in `handle_sse`:

```python
        server = create_server(auth, agent, token_manager)
```

**Step 7: Run all tests**

Run: `cd /home/bballou/grist-mcp/.worktrees/session-proxy && uv run pytest tests/unit/ -v`

Expected: PASS

**Step 8: Commit**

```bash
cd /home/bballou/grist-mcp/.worktrees/session-proxy
git add src/grist_mcp/main.py
git commit -m "feat(main): add /api/v1/proxy HTTP endpoint"
```

---

## Task 13: Integration Test - Full Flow

**Files:**
- Create: `tests/integration/test_session_proxy.py`

**Step 1: Write integration test**

Create `tests/integration/test_session_proxy.py`:

```python
"""Integration tests for session token proxy."""

import os
import pytest
import httpx


GRIST_MCP_URL = os.environ.get("GRIST_MCP_URL", "http://localhost:3000")
GRIST_MCP_TOKEN = os.environ.get("GRIST_MCP_TOKEN")


@pytest.fixture
def mcp_client():
    """Client for MCP SSE endpoint."""
    return httpx.Client(
        base_url=GRIST_MCP_URL,
        headers={"Authorization": f"Bearer {GRIST_MCP_TOKEN}"},
    )


@pytest.fixture
def proxy_client():
    """Client for proxy endpoint (session token set per-test)."""
    return httpx.Client(base_url=GRIST_MCP_URL)


@pytest.mark.integration
def test_full_session_proxy_flow(mcp_client, proxy_client):
    """Test: request token via MCP, use token to call proxy."""
    # This test requires a running grist-mcp server with proper config
    # Skip if not configured
    if not GRIST_MCP_TOKEN:
        pytest.skip("GRIST_MCP_TOKEN not set")

    # Step 1: Request session token (would be via MCP in real usage)
    # For integration test, we test the proxy endpoint directly
    # This is a placeholder - full MCP integration would use SSE

    # Step 2: Use proxy endpoint
    # Note: Need a valid session token to test this fully
    # For now, verify endpoint exists and rejects bad tokens

    response = proxy_client.post(
        "/api/v1/proxy",
        headers={"Authorization": "Bearer invalid_token"},
        json={"method": "list_tables"},
    )

    assert response.status_code == 401
    data = response.json()
    assert data["success"] is False
    assert data["code"] in ["INVALID_TOKEN", "TOKEN_EXPIRED"]
```

**Step 2: Commit**

```bash
cd /home/bballou/grist-mcp/.worktrees/session-proxy
git add tests/integration/test_session_proxy.py
git commit -m "test(integration): add session proxy integration test"
```

---

## Task 14: Final Verification

**Step 1: Run all unit tests**

Run: `cd /home/bballou/grist-mcp/.worktrees/session-proxy && uv run pytest tests/unit/ -v`

Expected: All tests pass

**Step 2: Run linting (if configured)**

Run: `cd /home/bballou/grist-mcp/.worktrees/session-proxy && uv run ruff check src/`

Expected: No errors (or fix any that appear)

**Step 3: Update CHANGELOG.md**

Add to CHANGELOG.md under a new version section:

```markdown
## [Unreleased]

### Added
- Session token proxy: agents can request short-lived tokens for bulk operations
- `get_proxy_documentation` MCP tool: returns complete proxy API spec
- `request_session_token` MCP tool: creates scoped session tokens
- `POST /api/v1/proxy` HTTP endpoint: accepts session tokens for direct API access
```

**Step 4: Commit changelog**

```bash
cd /home/bballou/grist-mcp/.worktrees/session-proxy
git add CHANGELOG.md
git commit -m "docs: update CHANGELOG for session proxy feature"
```

---

## Summary

This implementation adds:

1. **SessionTokenManager** (`src/grist_mcp/session.py`) - in-memory token storage with TTL
2. **Session tools** (`src/grist_mcp/tools/session.py`) - `get_proxy_documentation` and `request_session_token`
3. **Proxy handler** (`src/grist_mcp/proxy.py`) - request parsing and method dispatch
4. **HTTP endpoint** - `POST /api/v1/proxy` route in main.py
5. **Tests** - unit tests for all components, integration test scaffold

Total: 14 tasks, ~50 commits
