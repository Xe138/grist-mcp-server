# Grist MCP Server Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a dockerized MCP server that allows AI agents to interact with Grist documents using scoped access tokens.

**Architecture:** Single MCP server reading config from YAML, validating bearer tokens against defined scopes, proxying requests to Grist API. All configuration file-based, no database.

**Tech Stack:** Python 3.14, uv, mcp SDK, httpx, pyyaml, pytest

---

## Task 1: Project Setup

**Files:**
- Create: `pyproject.toml`
- Create: `src/grist_mcp/__init__.py`
- Create: `.gitignore`

**Step 1: Create pyproject.toml**

```toml
[project]
name = "grist-mcp"
version = "0.1.0"
description = "MCP server for AI agents to interact with Grist documents"
requires-python = ">=3.14"
dependencies = [
    "mcp>=1.0.0",
    "httpx>=0.27.0",
    "pyyaml>=6.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.24.0",
    "pytest-httpx>=0.32.0",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

**Step 2: Create package init**

```python
# src/grist_mcp/__init__.py
"""Grist MCP Server - AI agent access to Grist documents."""

__version__ = "0.1.0"
```

**Step 3: Create .gitignore**

```
__pycache__/
*.py[cod]
.venv/
.env
config.yaml
*.egg-info/
dist/
.pytest_cache/
```

**Step 4: Initialize uv and install dependencies**

Run: `uv sync`
Expected: Creates `.venv/` and `uv.lock`

**Step 5: Commit**

```bash
git add pyproject.toml src/grist_mcp/__init__.py .gitignore uv.lock
git commit -m "feat: initialize project with uv and dependencies"
```

---

## Task 2: Config Schema and Parsing

**Files:**
- Create: `src/grist_mcp/config.py`
- Create: `tests/test_config.py`
- Create: `config.yaml.example`

**Step 1: Write failing test for config loading**

```python
# tests/test_config.py
import pytest
from grist_mcp.config import load_config, Config, Document, Token, TokenScope


def test_load_config_parses_documents(tmp_path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text("""
documents:
  my-doc:
    url: https://grist.example.com
    doc_id: abc123
    api_key: secret-key

tokens: []
""")

    config = load_config(str(config_file))

    assert "my-doc" in config.documents
    doc = config.documents["my-doc"]
    assert doc.url == "https://grist.example.com"
    assert doc.doc_id == "abc123"
    assert doc.api_key == "secret-key"


def test_load_config_parses_tokens(tmp_path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text("""
documents:
  budget:
    url: https://grist.example.com
    doc_id: abc123
    api_key: key123

tokens:
  - token: my-secret-token
    name: test-agent
    scope:
      - document: budget
        permissions: [read, write]
""")

    config = load_config(str(config_file))

    assert len(config.tokens) == 1
    token = config.tokens[0]
    assert token.token == "my-secret-token"
    assert token.name == "test-agent"
    assert len(token.scope) == 1
    assert token.scope[0].document == "budget"
    assert token.scope[0].permissions == ["read", "write"]


def test_load_config_substitutes_env_vars(tmp_path, monkeypatch):
    monkeypatch.setenv("TEST_API_KEY", "env-secret-key")

    config_file = tmp_path / "config.yaml"
    config_file.write_text("""
documents:
  my-doc:
    url: https://grist.example.com
    doc_id: abc123
    api_key: ${TEST_API_KEY}

tokens: []
""")

    config = load_config(str(config_file))

    assert config.documents["my-doc"].api_key == "env-secret-key"


def test_load_config_raises_on_missing_env_var(tmp_path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text("""
documents:
  my-doc:
    url: https://grist.example.com
    doc_id: abc123
    api_key: ${MISSING_VAR}

tokens: []
""")

    with pytest.raises(ValueError, match="MISSING_VAR"):
        load_config(str(config_file))
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_config.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'grist_mcp.config'"

**Step 3: Implement config module**

```python
# src/grist_mcp/config.py
"""Configuration loading and parsing."""

import os
import re
from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass
class Document:
    """A Grist document configuration."""
    url: str
    doc_id: str
    api_key: str


@dataclass
class TokenScope:
    """Access scope for a single document."""
    document: str
    permissions: list[str]


@dataclass
class Token:
    """An agent token with its access scopes."""
    token: str
    name: str
    scope: list[TokenScope]


@dataclass
class Config:
    """Full server configuration."""
    documents: dict[str, Document]
    tokens: list[Token]


def _substitute_env_vars(value: str) -> str:
    """Replace ${VAR} patterns with environment variable values."""
    pattern = r'\$\{([^}]+)\}'

    def replacer(match: re.Match) -> str:
        var_name = match.group(1)
        env_value = os.environ.get(var_name)
        if env_value is None:
            raise ValueError(f"Environment variable not set: {var_name}")
        return env_value

    return re.sub(pattern, replacer, value)


def _substitute_env_vars_recursive(obj):
    """Recursively substitute env vars in a data structure."""
    if isinstance(obj, str):
        return _substitute_env_vars(obj)
    elif isinstance(obj, dict):
        return {k: _substitute_env_vars_recursive(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_substitute_env_vars_recursive(item) for item in obj]
    return obj


def load_config(config_path: str) -> Config:
    """Load and parse configuration from YAML file."""
    path = Path(config_path)
    raw = yaml.safe_load(path.read_text())

    # Substitute environment variables
    raw = _substitute_env_vars_recursive(raw)

    # Parse documents
    documents = {}
    for name, doc_data in raw.get("documents", {}).items():
        documents[name] = Document(
            url=doc_data["url"],
            doc_id=doc_data["doc_id"],
            api_key=doc_data["api_key"],
        )

    # Parse tokens
    tokens = []
    for token_data in raw.get("tokens", []):
        scope = [
            TokenScope(
                document=s["document"],
                permissions=s["permissions"],
            )
            for s in token_data.get("scope", [])
        ]
        tokens.append(Token(
            token=token_data["token"],
            name=token_data["name"],
            scope=scope,
        ))

    return Config(documents=documents, tokens=tokens)
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_config.py -v`
Expected: All 4 tests PASS

**Step 5: Create example config file**

```yaml
# config.yaml.example

# ============================================================
# Token Generation:
#   python -c "import secrets; print(secrets.token_urlsafe(32))"
#   openssl rand -base64 32
# ============================================================

# Document definitions (each is self-contained)
documents:
  budget-2024:
    url: https://work.getgrist.com
    doc_id: mK7xB2pQ9mN4v
    api_key: ${GRIST_WORK_API_KEY}

  expenses:
    url: https://work.getgrist.com
    doc_id: nL8yC3qR0oO5w
    api_key: ${GRIST_WORK_API_KEY}

  personal-tracker:
    url: https://docs.getgrist.com
    doc_id: pN0zE5sT2qP7x
    api_key: ${GRIST_PERSONAL_API_KEY}

# Agent tokens with access scopes
tokens:
  - token: REPLACE_WITH_GENERATED_TOKEN
    name: finance-agent
    scope:
      - document: budget-2024
        permissions: [read, write]
      - document: expenses
        permissions: [read]

  - token: REPLACE_WITH_ANOTHER_TOKEN
    name: analytics-agent
    scope:
      - document: personal-tracker
        permissions: [read, write, schema]
```

**Step 6: Commit**

```bash
git add src/grist_mcp/config.py tests/test_config.py config.yaml.example
git commit -m "feat: add config loading with env var substitution"
```

---

## Task 3: Authentication and Authorization

**Files:**
- Create: `src/grist_mcp/auth.py`
- Create: `tests/test_auth.py`

**Step 1: Write failing tests for auth**

```python
# tests/test_auth.py
import pytest
from grist_mcp.auth import Authenticator, AuthError, Permission
from grist_mcp.config import Config, Document, Token, TokenScope


@pytest.fixture
def sample_config():
    return Config(
        documents={
            "budget": Document(
                url="https://grist.example.com",
                doc_id="abc123",
                api_key="doc-api-key",
            ),
            "expenses": Document(
                url="https://grist.example.com",
                doc_id="def456",
                api_key="doc-api-key",
            ),
        },
        tokens=[
            Token(
                token="valid-token",
                name="test-agent",
                scope=[
                    TokenScope(document="budget", permissions=["read", "write"]),
                    TokenScope(document="expenses", permissions=["read"]),
                ],
            ),
        ],
    )


def test_authenticate_valid_token(sample_config):
    auth = Authenticator(sample_config)
    agent = auth.authenticate("valid-token")

    assert agent.name == "test-agent"
    assert agent.token == "valid-token"


def test_authenticate_invalid_token(sample_config):
    auth = Authenticator(sample_config)

    with pytest.raises(AuthError, match="Invalid token"):
        auth.authenticate("bad-token")


def test_authorize_allowed_document_and_permission(sample_config):
    auth = Authenticator(sample_config)
    agent = auth.authenticate("valid-token")

    # Should not raise
    auth.authorize(agent, "budget", Permission.READ)
    auth.authorize(agent, "budget", Permission.WRITE)
    auth.authorize(agent, "expenses", Permission.READ)


def test_authorize_denied_document(sample_config):
    auth = Authenticator(sample_config)
    agent = auth.authenticate("valid-token")

    with pytest.raises(AuthError, match="Document not in scope"):
        auth.authorize(agent, "unknown-doc", Permission.READ)


def test_authorize_denied_permission(sample_config):
    auth = Authenticator(sample_config)
    agent = auth.authenticate("valid-token")

    # expenses only has read permission
    with pytest.raises(AuthError, match="Permission denied"):
        auth.authorize(agent, "expenses", Permission.WRITE)


def test_get_accessible_documents(sample_config):
    auth = Authenticator(sample_config)
    agent = auth.authenticate("valid-token")

    docs = auth.get_accessible_documents(agent)

    assert len(docs) == 2
    assert {"name": "budget", "permissions": ["read", "write"]} in docs
    assert {"name": "expenses", "permissions": ["read"]} in docs
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_auth.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'grist_mcp.auth'"

**Step 3: Implement auth module**

```python
# src/grist_mcp/auth.py
"""Authentication and authorization."""

from dataclasses import dataclass
from enum import Enum

from grist_mcp.config import Config, Token


class Permission(Enum):
    """Document permission levels."""
    READ = "read"
    WRITE = "write"
    SCHEMA = "schema"


class AuthError(Exception):
    """Authentication or authorization error."""
    pass


@dataclass
class Agent:
    """An authenticated agent."""
    token: str
    name: str
    _token_obj: Token


class Authenticator:
    """Handles token validation and permission checking."""

    def __init__(self, config: Config):
        self._config = config
        self._token_map = {t.token: t for t in config.tokens}

    def authenticate(self, token: str) -> Agent:
        """Validate token and return Agent object."""
        token_obj = self._token_map.get(token)
        if token_obj is None:
            raise AuthError("Invalid token")

        return Agent(
            token=token,
            name=token_obj.name,
            _token_obj=token_obj,
        )

    def authorize(self, agent: Agent, document: str, permission: Permission) -> None:
        """Check if agent has permission on document. Raises AuthError if not."""
        # Find the scope entry for this document
        scope_entry = None
        for scope in agent._token_obj.scope:
            if scope.document == document:
                scope_entry = scope
                break

        if scope_entry is None:
            raise AuthError("Document not in scope")

        if permission.value not in scope_entry.permissions:
            raise AuthError("Permission denied")

    def get_accessible_documents(self, agent: Agent) -> list[dict]:
        """Return list of documents agent can access with their permissions."""
        return [
            {"name": scope.document, "permissions": scope.permissions}
            for scope in agent._token_obj.scope
        ]

    def get_document(self, document_name: str):
        """Get document config by name."""
        return self._config.documents.get(document_name)
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_auth.py -v`
Expected: All 6 tests PASS

**Step 5: Commit**

```bash
git add src/grist_mcp/auth.py tests/test_auth.py
git commit -m "feat: add authentication and authorization"
```

---

## Task 4: Grist API Client

**Files:**
- Create: `src/grist_mcp/grist_client.py`
- Create: `tests/test_grist_client.py`

**Step 1: Write failing tests for Grist client**

```python
# tests/test_grist_client.py
import pytest
from pytest_httpx import HTTPXMock

from grist_mcp.grist_client import GristClient
from grist_mcp.config import Document


@pytest.fixture
def doc():
    return Document(
        url="https://grist.example.com",
        doc_id="abc123",
        api_key="test-api-key",
    )


@pytest.fixture
def client(doc):
    return GristClient(doc)


@pytest.mark.asyncio
async def test_list_tables(client, httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        url="https://grist.example.com/api/docs/abc123/tables",
        json={"tables": [{"id": "Table1"}, {"id": "Table2"}]},
    )

    tables = await client.list_tables()

    assert tables == ["Table1", "Table2"]


@pytest.mark.asyncio
async def test_describe_table(client, httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        url="https://grist.example.com/api/docs/abc123/tables/Table1/columns",
        json={
            "columns": [
                {"id": "Name", "fields": {"type": "Text", "formula": ""}},
                {"id": "Amount", "fields": {"type": "Numeric", "formula": "$Price * $Qty"}},
            ]
        },
    )

    columns = await client.describe_table("Table1")

    assert len(columns) == 2
    assert columns[0] == {"id": "Name", "type": "Text", "formula": ""}
    assert columns[1] == {"id": "Amount", "type": "Numeric", "formula": "$Price * $Qty"}


@pytest.mark.asyncio
async def test_get_records(client, httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        url="https://grist.example.com/api/docs/abc123/tables/Table1/records",
        json={
            "records": [
                {"id": 1, "fields": {"Name": "Alice", "Amount": 100}},
                {"id": 2, "fields": {"Name": "Bob", "Amount": 200}},
            ]
        },
    )

    records = await client.get_records("Table1")

    assert len(records) == 2
    assert records[0] == {"id": 1, "Name": "Alice", "Amount": 100}


@pytest.mark.asyncio
async def test_add_records(client, httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        url="https://grist.example.com/api/docs/abc123/tables/Table1/records",
        method="POST",
        json={"records": [{"id": 3}, {"id": 4}]},
    )

    ids = await client.add_records("Table1", [
        {"Name": "Charlie", "Amount": 300},
        {"Name": "Diana", "Amount": 400},
    ])

    assert ids == [3, 4]


@pytest.mark.asyncio
async def test_update_records(client, httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        url="https://grist.example.com/api/docs/abc123/tables/Table1/records",
        method="PATCH",
        json={},
    )

    # Should not raise
    await client.update_records("Table1", [
        {"id": 1, "fields": {"Amount": 150}},
    ])


@pytest.mark.asyncio
async def test_delete_records(client, httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        url="https://grist.example.com/api/docs/abc123/tables/Table1/data/delete",
        method="POST",
        json={},
    )

    # Should not raise
    await client.delete_records("Table1", [1, 2])


@pytest.mark.asyncio
async def test_sql_query(client, httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        url="https://grist.example.com/api/docs/abc123/sql",
        method="GET",
        json={
            "statement": "SELECT * FROM Table1",
            "records": [
                {"fields": {"Name": "Alice", "Amount": 100}},
            ],
        },
    )

    result = await client.sql_query("SELECT * FROM Table1")

    assert result == [{"Name": "Alice", "Amount": 100}]


@pytest.mark.asyncio
async def test_create_table(client, httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        url="https://grist.example.com/api/docs/abc123/tables",
        method="POST",
        json={"tables": [{"id": "NewTable"}]},
    )

    table_id = await client.create_table("NewTable", [
        {"id": "Col1", "type": "Text"},
        {"id": "Col2", "type": "Numeric"},
    ])

    assert table_id == "NewTable"


@pytest.mark.asyncio
async def test_add_column(client, httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        url="https://grist.example.com/api/docs/abc123/tables/Table1/columns",
        method="POST",
        json={"columns": [{"id": "NewCol"}]},
    )

    col_id = await client.add_column("Table1", "NewCol", "Text", formula=None)

    assert col_id == "NewCol"


@pytest.mark.asyncio
async def test_modify_column(client, httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        url="https://grist.example.com/api/docs/abc123/tables/Table1/columns/Amount",
        method="PATCH",
        json={},
    )

    # Should not raise
    await client.modify_column("Table1", "Amount", type="Int", formula="$Price * $Qty")


@pytest.mark.asyncio
async def test_delete_column(client, httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        url="https://grist.example.com/api/docs/abc123/tables/Table1/columns/OldCol",
        method="DELETE",
        json={},
    )

    # Should not raise
    await client.delete_column("Table1", "OldCol")
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_grist_client.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'grist_mcp.grist_client'"

**Step 3: Implement Grist client**

```python
# src/grist_mcp/grist_client.py
"""Grist API client."""

import httpx

from grist_mcp.config import Document


class GristClient:
    """Async client for Grist API operations."""

    def __init__(self, document: Document):
        self._doc = document
        self._base_url = f"{document.url.rstrip('/')}/api/docs/{document.doc_id}"
        self._headers = {"Authorization": f"Bearer {document.api_key}"}

    async def _request(self, method: str, path: str, **kwargs) -> dict:
        """Make an authenticated request to Grist API."""
        async with httpx.AsyncClient() as client:
            response = await client.request(
                method,
                f"{self._base_url}{path}",
                headers=self._headers,
                **kwargs,
            )
            response.raise_for_status()
            return response.json() if response.content else {}

    # Read operations

    async def list_tables(self) -> list[str]:
        """List all tables in the document."""
        data = await self._request("GET", "/tables")
        return [t["id"] for t in data.get("tables", [])]

    async def describe_table(self, table: str) -> list[dict]:
        """Get column information for a table."""
        data = await self._request("GET", f"/tables/{table}/columns")
        return [
            {
                "id": col["id"],
                "type": col["fields"].get("type", "Any"),
                "formula": col["fields"].get("formula", ""),
            }
            for col in data.get("columns", [])
        ]

    async def get_records(
        self,
        table: str,
        filter: dict | None = None,
        sort: str | None = None,
        limit: int | None = None,
    ) -> list[dict]:
        """Fetch records from a table."""
        params = {}
        if filter:
            params["filter"] = filter
        if sort:
            params["sort"] = sort
        if limit:
            params["limit"] = limit

        data = await self._request("GET", f"/tables/{table}/records", params=params)

        return [
            {"id": r["id"], **r["fields"]}
            for r in data.get("records", [])
        ]

    async def sql_query(self, sql: str) -> list[dict]:
        """Run a read-only SQL query."""
        data = await self._request("GET", "/sql", params={"q": sql})
        return [r["fields"] for r in data.get("records", [])]

    # Write operations

    async def add_records(self, table: str, records: list[dict]) -> list[int]:
        """Add records to a table. Returns list of new record IDs."""
        payload = {
            "records": [{"fields": r} for r in records]
        }
        data = await self._request("POST", f"/tables/{table}/records", json=payload)
        return [r["id"] for r in data.get("records", [])]

    async def update_records(self, table: str, records: list[dict]) -> None:
        """Update records. Each record must have 'id' and 'fields' keys."""
        payload = {"records": records}
        await self._request("PATCH", f"/tables/{table}/records", json=payload)

    async def delete_records(self, table: str, record_ids: list[int]) -> None:
        """Delete records by ID."""
        await self._request("POST", f"/tables/{table}/data/delete", json=record_ids)

    # Schema operations

    async def create_table(self, table_id: str, columns: list[dict]) -> str:
        """Create a new table with columns. Returns table ID."""
        payload = {
            "tables": [{
                "id": table_id,
                "columns": [
                    {"id": c["id"], "fields": {"type": c["type"]}}
                    for c in columns
                ],
            }]
        }
        data = await self._request("POST", "/tables", json=payload)
        return data["tables"][0]["id"]

    async def add_column(
        self,
        table: str,
        column_id: str,
        column_type: str,
        formula: str | None = None,
    ) -> str:
        """Add a column to a table. Returns column ID."""
        fields = {"type": column_type}
        if formula:
            fields["formula"] = formula

        payload = {"columns": [{"id": column_id, "fields": fields}]}
        data = await self._request("POST", f"/tables/{table}/columns", json=payload)
        return data["columns"][0]["id"]

    async def modify_column(
        self,
        table: str,
        column_id: str,
        type: str | None = None,
        formula: str | None = None,
    ) -> None:
        """Modify a column's type or formula."""
        fields = {}
        if type is not None:
            fields["type"] = type
        if formula is not None:
            fields["formula"] = formula

        await self._request("PATCH", f"/tables/{table}/columns/{column_id}", json={"fields": fields})

    async def delete_column(self, table: str, column_id: str) -> None:
        """Delete a column from a table."""
        await self._request("DELETE", f"/tables/{table}/columns/{column_id}")
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_grist_client.py -v`
Expected: All 12 tests PASS

**Step 5: Commit**

```bash
git add src/grist_mcp/grist_client.py tests/test_grist_client.py
git commit -m "feat: add Grist API client"
```

---

## Task 5: MCP Tools - Discovery

**Files:**
- Create: `src/grist_mcp/tools/__init__.py`
- Create: `src/grist_mcp/tools/discovery.py`
- Create: `tests/test_tools_discovery.py`

**Step 1: Write failing test for list_documents tool**

```python
# tests/test_tools_discovery.py
import pytest
from grist_mcp.tools.discovery import list_documents
from grist_mcp.auth import Agent
from grist_mcp.config import Token, TokenScope


@pytest.fixture
def agent():
    token_obj = Token(
        token="test-token",
        name="test-agent",
        scope=[
            TokenScope(document="budget", permissions=["read", "write"]),
            TokenScope(document="expenses", permissions=["read"]),
        ],
    )
    return Agent(token="test-token", name="test-agent", _token_obj=token_obj)


@pytest.mark.asyncio
async def test_list_documents_returns_accessible_docs(agent):
    result = await list_documents(agent)

    assert result == {
        "documents": [
            {"name": "budget", "permissions": ["read", "write"]},
            {"name": "expenses", "permissions": ["read"]},
        ]
    }
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_tools_discovery.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'grist_mcp.tools'"

**Step 3: Implement discovery tools**

```python
# src/grist_mcp/tools/__init__.py
"""MCP tools for Grist operations."""
```

```python
# src/grist_mcp/tools/discovery.py
"""Discovery tools - list accessible documents."""

from grist_mcp.auth import Agent


async def list_documents(agent: Agent) -> dict:
    """List documents this agent can access with their permissions."""
    documents = [
        {"name": scope.document, "permissions": scope.permissions}
        for scope in agent._token_obj.scope
    ]
    return {"documents": documents}
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_tools_discovery.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/grist_mcp/tools/__init__.py src/grist_mcp/tools/discovery.py tests/test_tools_discovery.py
git commit -m "feat: add list_documents discovery tool"
```

---

## Task 6: MCP Tools - Read Operations

**Files:**
- Create: `src/grist_mcp/tools/read.py`
- Create: `tests/test_tools_read.py`

**Step 1: Write failing tests for read tools**

```python
# tests/test_tools_read.py
import pytest
from unittest.mock import AsyncMock, MagicMock

from grist_mcp.tools.read import list_tables, describe_table, get_records, sql_query
from grist_mcp.auth import Authenticator, Agent, Permission
from grist_mcp.config import Config, Document, Token, TokenScope


@pytest.fixture
def config():
    return Config(
        documents={
            "budget": Document(
                url="https://grist.example.com",
                doc_id="abc123",
                api_key="key",
            ),
        },
        tokens=[
            Token(
                token="test-token",
                name="test-agent",
                scope=[TokenScope(document="budget", permissions=["read"])],
            ),
        ],
    )


@pytest.fixture
def auth(config):
    return Authenticator(config)


@pytest.fixture
def agent(auth):
    return auth.authenticate("test-token")


@pytest.fixture
def mock_client():
    client = AsyncMock()
    client.list_tables.return_value = ["Table1", "Table2"]
    client.describe_table.return_value = [
        {"id": "Name", "type": "Text", "formula": ""},
    ]
    client.get_records.return_value = [
        {"id": 1, "Name": "Alice"},
    ]
    client.sql_query.return_value = [{"Name": "Alice"}]
    return client


@pytest.mark.asyncio
async def test_list_tables(agent, auth, mock_client):
    result = await list_tables(agent, auth, "budget", client=mock_client)

    assert result == {"tables": ["Table1", "Table2"]}
    mock_client.list_tables.assert_called_once()


@pytest.mark.asyncio
async def test_describe_table(agent, auth, mock_client):
    result = await describe_table(agent, auth, "budget", "Table1", client=mock_client)

    assert result == {
        "table": "Table1",
        "columns": [{"id": "Name", "type": "Text", "formula": ""}],
    }


@pytest.mark.asyncio
async def test_get_records(agent, auth, mock_client):
    result = await get_records(agent, auth, "budget", "Table1", client=mock_client)

    assert result == {"records": [{"id": 1, "Name": "Alice"}]}


@pytest.mark.asyncio
async def test_sql_query(agent, auth, mock_client):
    result = await sql_query(agent, auth, "budget", "SELECT * FROM Table1", client=mock_client)

    assert result == {"records": [{"Name": "Alice"}]}
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_tools_read.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'grist_mcp.tools.read'"

**Step 3: Implement read tools**

```python
# src/grist_mcp/tools/read.py
"""Read tools - query tables and records."""

from grist_mcp.auth import Agent, Authenticator, Permission
from grist_mcp.grist_client import GristClient


async def list_tables(
    agent: Agent,
    auth: Authenticator,
    document: str,
    client: GristClient | None = None,
) -> dict:
    """List all tables in a document."""
    auth.authorize(agent, document, Permission.READ)

    if client is None:
        doc = auth.get_document(document)
        client = GristClient(doc)

    tables = await client.list_tables()
    return {"tables": tables}


async def describe_table(
    agent: Agent,
    auth: Authenticator,
    document: str,
    table: str,
    client: GristClient | None = None,
) -> dict:
    """Get column information for a table."""
    auth.authorize(agent, document, Permission.READ)

    if client is None:
        doc = auth.get_document(document)
        client = GristClient(doc)

    columns = await client.describe_table(table)
    return {"table": table, "columns": columns}


async def get_records(
    agent: Agent,
    auth: Authenticator,
    document: str,
    table: str,
    filter: dict | None = None,
    sort: str | None = None,
    limit: int | None = None,
    client: GristClient | None = None,
) -> dict:
    """Fetch records from a table."""
    auth.authorize(agent, document, Permission.READ)

    if client is None:
        doc = auth.get_document(document)
        client = GristClient(doc)

    records = await client.get_records(table, filter=filter, sort=sort, limit=limit)
    return {"records": records}


async def sql_query(
    agent: Agent,
    auth: Authenticator,
    document: str,
    query: str,
    client: GristClient | None = None,
) -> dict:
    """Run a read-only SQL query."""
    auth.authorize(agent, document, Permission.READ)

    if client is None:
        doc = auth.get_document(document)
        client = GristClient(doc)

    records = await client.sql_query(query)
    return {"records": records}
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_tools_read.py -v`
Expected: All 4 tests PASS

**Step 5: Commit**

```bash
git add src/grist_mcp/tools/read.py tests/test_tools_read.py
git commit -m "feat: add read tools (list_tables, describe_table, get_records, sql_query)"
```

---

## Task 7: MCP Tools - Write Operations

**Files:**
- Create: `src/grist_mcp/tools/write.py`
- Create: `tests/test_tools_write.py`

**Step 1: Write failing tests for write tools**

```python
# tests/test_tools_write.py
import pytest
from unittest.mock import AsyncMock

from grist_mcp.tools.write import add_records, update_records, delete_records
from grist_mcp.auth import Authenticator, AuthError
from grist_mcp.config import Config, Document, Token, TokenScope


@pytest.fixture
def config():
    return Config(
        documents={
            "budget": Document(
                url="https://grist.example.com",
                doc_id="abc123",
                api_key="key",
            ),
        },
        tokens=[
            Token(
                token="write-token",
                name="write-agent",
                scope=[TokenScope(document="budget", permissions=["read", "write"])],
            ),
            Token(
                token="read-token",
                name="read-agent",
                scope=[TokenScope(document="budget", permissions=["read"])],
            ),
        ],
    )


@pytest.fixture
def auth(config):
    return Authenticator(config)


@pytest.fixture
def mock_client():
    client = AsyncMock()
    client.add_records.return_value = [1, 2]
    client.update_records.return_value = None
    client.delete_records.return_value = None
    return client


@pytest.mark.asyncio
async def test_add_records(auth, mock_client):
    agent = auth.authenticate("write-token")

    result = await add_records(
        agent, auth, "budget", "Table1",
        records=[{"Name": "Alice"}, {"Name": "Bob"}],
        client=mock_client,
    )

    assert result == {"inserted_ids": [1, 2]}


@pytest.mark.asyncio
async def test_add_records_denied_without_write(auth, mock_client):
    agent = auth.authenticate("read-token")

    with pytest.raises(AuthError, match="Permission denied"):
        await add_records(
            agent, auth, "budget", "Table1",
            records=[{"Name": "Alice"}],
            client=mock_client,
        )


@pytest.mark.asyncio
async def test_update_records(auth, mock_client):
    agent = auth.authenticate("write-token")

    result = await update_records(
        agent, auth, "budget", "Table1",
        records=[{"id": 1, "fields": {"Name": "Updated"}}],
        client=mock_client,
    )

    assert result == {"updated": True}


@pytest.mark.asyncio
async def test_delete_records(auth, mock_client):
    agent = auth.authenticate("write-token")

    result = await delete_records(
        agent, auth, "budget", "Table1",
        record_ids=[1, 2],
        client=mock_client,
    )

    assert result == {"deleted": True}
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_tools_write.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'grist_mcp.tools.write'"

**Step 3: Implement write tools**

```python
# src/grist_mcp/tools/write.py
"""Write tools - create, update, delete records."""

from grist_mcp.auth import Agent, Authenticator, Permission
from grist_mcp.grist_client import GristClient


async def add_records(
    agent: Agent,
    auth: Authenticator,
    document: str,
    table: str,
    records: list[dict],
    client: GristClient | None = None,
) -> dict:
    """Add records to a table."""
    auth.authorize(agent, document, Permission.WRITE)

    if client is None:
        doc = auth.get_document(document)
        client = GristClient(doc)

    ids = await client.add_records(table, records)
    return {"inserted_ids": ids}


async def update_records(
    agent: Agent,
    auth: Authenticator,
    document: str,
    table: str,
    records: list[dict],
    client: GristClient | None = None,
) -> dict:
    """Update existing records."""
    auth.authorize(agent, document, Permission.WRITE)

    if client is None:
        doc = auth.get_document(document)
        client = GristClient(doc)

    await client.update_records(table, records)
    return {"updated": True}


async def delete_records(
    agent: Agent,
    auth: Authenticator,
    document: str,
    table: str,
    record_ids: list[int],
    client: GristClient | None = None,
) -> dict:
    """Delete records by ID."""
    auth.authorize(agent, document, Permission.WRITE)

    if client is None:
        doc = auth.get_document(document)
        client = GristClient(doc)

    await client.delete_records(table, record_ids)
    return {"deleted": True}
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_tools_write.py -v`
Expected: All 4 tests PASS

**Step 5: Commit**

```bash
git add src/grist_mcp/tools/write.py tests/test_tools_write.py
git commit -m "feat: add write tools (add_records, update_records, delete_records)"
```

---

## Task 8: MCP Tools - Schema Operations

**Files:**
- Create: `src/grist_mcp/tools/schema.py`
- Create: `tests/test_tools_schema.py`

**Step 1: Write failing tests for schema tools**

```python
# tests/test_tools_schema.py
import pytest
from unittest.mock import AsyncMock

from grist_mcp.tools.schema import create_table, add_column, modify_column, delete_column
from grist_mcp.auth import Authenticator, AuthError
from grist_mcp.config import Config, Document, Token, TokenScope


@pytest.fixture
def config():
    return Config(
        documents={
            "budget": Document(
                url="https://grist.example.com",
                doc_id="abc123",
                api_key="key",
            ),
        },
        tokens=[
            Token(
                token="schema-token",
                name="schema-agent",
                scope=[TokenScope(document="budget", permissions=["read", "write", "schema"])],
            ),
            Token(
                token="write-token",
                name="write-agent",
                scope=[TokenScope(document="budget", permissions=["read", "write"])],
            ),
        ],
    )


@pytest.fixture
def auth(config):
    return Authenticator(config)


@pytest.fixture
def mock_client():
    client = AsyncMock()
    client.create_table.return_value = "NewTable"
    client.add_column.return_value = "NewCol"
    client.modify_column.return_value = None
    client.delete_column.return_value = None
    return client


@pytest.mark.asyncio
async def test_create_table(auth, mock_client):
    agent = auth.authenticate("schema-token")

    result = await create_table(
        agent, auth, "budget", "NewTable",
        columns=[{"id": "Name", "type": "Text"}],
        client=mock_client,
    )

    assert result == {"table_id": "NewTable"}


@pytest.mark.asyncio
async def test_create_table_denied_without_schema(auth, mock_client):
    agent = auth.authenticate("write-token")

    with pytest.raises(AuthError, match="Permission denied"):
        await create_table(
            agent, auth, "budget", "NewTable",
            columns=[{"id": "Name", "type": "Text"}],
            client=mock_client,
        )


@pytest.mark.asyncio
async def test_add_column(auth, mock_client):
    agent = auth.authenticate("schema-token")

    result = await add_column(
        agent, auth, "budget", "Table1", "NewCol", "Text",
        client=mock_client,
    )

    assert result == {"column_id": "NewCol"}


@pytest.mark.asyncio
async def test_modify_column(auth, mock_client):
    agent = auth.authenticate("schema-token")

    result = await modify_column(
        agent, auth, "budget", "Table1", "Col1",
        type="Int",
        formula="$A + $B",
        client=mock_client,
    )

    assert result == {"modified": True}


@pytest.mark.asyncio
async def test_delete_column(auth, mock_client):
    agent = auth.authenticate("schema-token")

    result = await delete_column(
        agent, auth, "budget", "Table1", "OldCol",
        client=mock_client,
    )

    assert result == {"deleted": True}
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_tools_schema.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'grist_mcp.tools.schema'"

**Step 3: Implement schema tools**

```python
# src/grist_mcp/tools/schema.py
"""Schema tools - create and modify tables and columns."""

from grist_mcp.auth import Agent, Authenticator, Permission
from grist_mcp.grist_client import GristClient


async def create_table(
    agent: Agent,
    auth: Authenticator,
    document: str,
    table_id: str,
    columns: list[dict],
    client: GristClient | None = None,
) -> dict:
    """Create a new table with columns."""
    auth.authorize(agent, document, Permission.SCHEMA)

    if client is None:
        doc = auth.get_document(document)
        client = GristClient(doc)

    created_id = await client.create_table(table_id, columns)
    return {"table_id": created_id}


async def add_column(
    agent: Agent,
    auth: Authenticator,
    document: str,
    table: str,
    column_id: str,
    column_type: str,
    formula: str | None = None,
    client: GristClient | None = None,
) -> dict:
    """Add a column to a table."""
    auth.authorize(agent, document, Permission.SCHEMA)

    if client is None:
        doc = auth.get_document(document)
        client = GristClient(doc)

    created_id = await client.add_column(table, column_id, column_type, formula=formula)
    return {"column_id": created_id}


async def modify_column(
    agent: Agent,
    auth: Authenticator,
    document: str,
    table: str,
    column_id: str,
    type: str | None = None,
    formula: str | None = None,
    client: GristClient | None = None,
) -> dict:
    """Modify a column's type or formula."""
    auth.authorize(agent, document, Permission.SCHEMA)

    if client is None:
        doc = auth.get_document(document)
        client = GristClient(doc)

    await client.modify_column(table, column_id, type=type, formula=formula)
    return {"modified": True}


async def delete_column(
    agent: Agent,
    auth: Authenticator,
    document: str,
    table: str,
    column_id: str,
    client: GristClient | None = None,
) -> dict:
    """Delete a column from a table."""
    auth.authorize(agent, document, Permission.SCHEMA)

    if client is None:
        doc = auth.get_document(document)
        client = GristClient(doc)

    await client.delete_column(table, column_id)
    return {"deleted": True}
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_tools_schema.py -v`
Expected: All 5 tests PASS

**Step 5: Commit**

```bash
git add src/grist_mcp/tools/schema.py tests/test_tools_schema.py
git commit -m "feat: add schema tools (create_table, add_column, modify_column, delete_column)"
```

---

## Task 9: MCP Server Entry Point

**Files:**
- Create: `src/grist_mcp/server.py`
- Create: `src/grist_mcp/main.py`
- Create: `tests/test_server.py`

**Step 1: Write failing test for server**

```python
# tests/test_server.py
import pytest
from grist_mcp.server import create_server


def test_create_server_registers_tools(tmp_path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text("""
documents:
  test-doc:
    url: https://grist.example.com
    doc_id: abc123
    api_key: test-key

tokens:
  - token: test-token
    name: test-agent
    scope:
      - document: test-doc
        permissions: [read, write, schema]
""")

    server = create_server(str(config_file))

    # Server should have tools registered
    assert server is not None
    # Check tool names are registered
    tool_names = [t.name for t in server.list_tools()]
    assert "list_documents" in tool_names
    assert "list_tables" in tool_names
    assert "get_records" in tool_names
    assert "add_records" in tool_names
    assert "create_table" in tool_names
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_server.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'grist_mcp.server'"

**Step 3: Implement server module**

```python
# src/grist_mcp/server.py
"""MCP server setup and tool registration."""

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from grist_mcp.config import load_config
from grist_mcp.auth import Authenticator, AuthError, Agent

from grist_mcp.tools.discovery import list_documents as _list_documents
from grist_mcp.tools.read import list_tables as _list_tables
from grist_mcp.tools.read import describe_table as _describe_table
from grist_mcp.tools.read import get_records as _get_records
from grist_mcp.tools.read import sql_query as _sql_query
from grist_mcp.tools.write import add_records as _add_records
from grist_mcp.tools.write import update_records as _update_records
from grist_mcp.tools.write import delete_records as _delete_records
from grist_mcp.tools.schema import create_table as _create_table
from grist_mcp.tools.schema import add_column as _add_column
from grist_mcp.tools.schema import modify_column as _modify_column
from grist_mcp.tools.schema import delete_column as _delete_column


def create_server(config_path: str) -> Server:
    """Create and configure the MCP server."""
    config = load_config(config_path)
    auth = Authenticator(config)
    server = Server("grist-mcp")

    # Current agent context (set during authentication)
    _current_agent: Agent | None = None

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        return [
            Tool(
                name="list_documents",
                description="List documents this agent can access with their permissions",
                inputSchema={"type": "object", "properties": {}, "required": []},
            ),
            Tool(
                name="list_tables",
                description="List all tables in a document",
                inputSchema={
                    "type": "object",
                    "properties": {"document": {"type": "string", "description": "Document name"}},
                    "required": ["document"],
                },
            ),
            Tool(
                name="describe_table",
                description="Get column information for a table",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "document": {"type": "string"},
                        "table": {"type": "string"},
                    },
                    "required": ["document", "table"],
                },
            ),
            Tool(
                name="get_records",
                description="Fetch records from a table",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "document": {"type": "string"},
                        "table": {"type": "string"},
                        "filter": {"type": "object"},
                        "sort": {"type": "string"},
                        "limit": {"type": "integer"},
                    },
                    "required": ["document", "table"],
                },
            ),
            Tool(
                name="sql_query",
                description="Run a read-only SQL query against a document",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "document": {"type": "string"},
                        "query": {"type": "string"},
                    },
                    "required": ["document", "query"],
                },
            ),
            Tool(
                name="add_records",
                description="Add records to a table",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "document": {"type": "string"},
                        "table": {"type": "string"},
                        "records": {"type": "array", "items": {"type": "object"}},
                    },
                    "required": ["document", "table", "records"],
                },
            ),
            Tool(
                name="update_records",
                description="Update existing records",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "document": {"type": "string"},
                        "table": {"type": "string"},
                        "records": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "id": {"type": "integer"},
                                    "fields": {"type": "object"},
                                },
                            },
                        },
                    },
                    "required": ["document", "table", "records"],
                },
            ),
            Tool(
                name="delete_records",
                description="Delete records by ID",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "document": {"type": "string"},
                        "table": {"type": "string"},
                        "record_ids": {"type": "array", "items": {"type": "integer"}},
                    },
                    "required": ["document", "table", "record_ids"],
                },
            ),
            Tool(
                name="create_table",
                description="Create a new table with columns",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "document": {"type": "string"},
                        "table_id": {"type": "string"},
                        "columns": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "id": {"type": "string"},
                                    "type": {"type": "string"},
                                },
                            },
                        },
                    },
                    "required": ["document", "table_id", "columns"],
                },
            ),
            Tool(
                name="add_column",
                description="Add a column to a table",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "document": {"type": "string"},
                        "table": {"type": "string"},
                        "column_id": {"type": "string"},
                        "column_type": {"type": "string"},
                        "formula": {"type": "string"},
                    },
                    "required": ["document", "table", "column_id", "column_type"],
                },
            ),
            Tool(
                name="modify_column",
                description="Modify a column's type or formula",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "document": {"type": "string"},
                        "table": {"type": "string"},
                        "column_id": {"type": "string"},
                        "type": {"type": "string"},
                        "formula": {"type": "string"},
                    },
                    "required": ["document", "table", "column_id"],
                },
            ),
            Tool(
                name="delete_column",
                description="Delete a column from a table",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "document": {"type": "string"},
                        "table": {"type": "string"},
                        "column_id": {"type": "string"},
                    },
                    "required": ["document", "table", "column_id"],
                },
            ),
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict) -> list[TextContent]:
        nonlocal _current_agent

        if _current_agent is None:
            return [TextContent(type="text", text="Error: Not authenticated")]

        try:
            if name == "list_documents":
                result = await _list_documents(_current_agent)
            elif name == "list_tables":
                result = await _list_tables(_current_agent, auth, arguments["document"])
            elif name == "describe_table":
                result = await _describe_table(
                    _current_agent, auth, arguments["document"], arguments["table"]
                )
            elif name == "get_records":
                result = await _get_records(
                    _current_agent, auth, arguments["document"], arguments["table"],
                    filter=arguments.get("filter"),
                    sort=arguments.get("sort"),
                    limit=arguments.get("limit"),
                )
            elif name == "sql_query":
                result = await _sql_query(
                    _current_agent, auth, arguments["document"], arguments["query"]
                )
            elif name == "add_records":
                result = await _add_records(
                    _current_agent, auth, arguments["document"], arguments["table"],
                    arguments["records"],
                )
            elif name == "update_records":
                result = await _update_records(
                    _current_agent, auth, arguments["document"], arguments["table"],
                    arguments["records"],
                )
            elif name == "delete_records":
                result = await _delete_records(
                    _current_agent, auth, arguments["document"], arguments["table"],
                    arguments["record_ids"],
                )
            elif name == "create_table":
                result = await _create_table(
                    _current_agent, auth, arguments["document"], arguments["table_id"],
                    arguments["columns"],
                )
            elif name == "add_column":
                result = await _add_column(
                    _current_agent, auth, arguments["document"], arguments["table"],
                    arguments["column_id"], arguments["column_type"],
                    formula=arguments.get("formula"),
                )
            elif name == "modify_column":
                result = await _modify_column(
                    _current_agent, auth, arguments["document"], arguments["table"],
                    arguments["column_id"],
                    type=arguments.get("type"),
                    formula=arguments.get("formula"),
                )
            elif name == "delete_column":
                result = await _delete_column(
                    _current_agent, auth, arguments["document"], arguments["table"],
                    arguments["column_id"],
                )
            else:
                return [TextContent(type="text", text=f"Unknown tool: {name}")]

            import json
            return [TextContent(type="text", text=json.dumps(result))]

        except AuthError as e:
            return [TextContent(type="text", text=f"Authorization error: {e}")]
        except Exception as e:
            return [TextContent(type="text", text=f"Error: {e}")]

    # Store auth for external access
    server._auth = auth
    server._set_agent = lambda agent: setattr(server, '_current_agent', agent) or setattr(type(server), '_current_agent', agent)

    return server
```

```python
# src/grist_mcp/main.py
"""Main entry point for the MCP server."""

import asyncio
import os
import sys

from mcp.server.stdio import stdio_server

from grist_mcp.server import create_server


async def main():
    config_path = os.environ.get("CONFIG_PATH", "/app/config.yaml")

    if not os.path.exists(config_path):
        print(f"Error: Config file not found at {config_path}", file=sys.stderr)
        sys.exit(1)

    server = create_server(config_path)

    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_server.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/grist_mcp/server.py src/grist_mcp/main.py tests/test_server.py
git commit -m "feat: add MCP server with all tools registered"
```

---

## Task 10: Docker Setup

**Files:**
- Create: `Dockerfile`
- Create: `docker-compose.yaml`
- Create: `.env.example`

**Step 1: Create Dockerfile**

```dockerfile
FROM ghcr.io/astral-sh/uv:python3.14-bookworm-slim

WORKDIR /app

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install dependencies
RUN uv sync --frozen --no-dev

# Copy source code
COPY src/ ./src/

# Default config path
ENV CONFIG_PATH=/app/config.yaml

# Run the server
CMD ["uv", "run", "python", "-m", "grist_mcp.main"]
```

**Step 2: Create docker-compose.yaml**

```yaml
services:
  grist-mcp:
    build: .
    ports:
      - "8080:8080"
    volumes:
      - ./config.yaml:/app/config.yaml:ro
    env_file:
      - .env
    environment:
      - CONFIG_PATH=/app/config.yaml
```

**Step 3: Create .env.example**

```bash
# Grist API keys - replace with your actual keys
GRIST_WORK_API_KEY=your-work-api-key-here
GRIST_PERSONAL_API_KEY=your-personal-api-key-here
```

**Step 4: Build and verify Docker image**

Run: `docker build -t grist-mcp:latest .`
Expected: Build completes successfully

**Step 5: Commit**

```bash
git add Dockerfile docker-compose.yaml .env.example
git commit -m "feat: add Docker configuration"
```

---

## Task 11: Tests Init and Final Verification

**Files:**
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`

**Step 1: Create test init and conftest**

```python
# tests/__init__.py
"""Test suite for grist-mcp."""
```

```python
# tests/conftest.py
"""Shared test fixtures."""

import pytest


@pytest.fixture
def sample_config_yaml():
    return """
documents:
  test-doc:
    url: https://grist.example.com
    doc_id: abc123
    api_key: test-key

tokens:
  - token: test-token
    name: test-agent
    scope:
      - document: test-doc
        permissions: [read, write, schema]
"""
```

**Step 2: Run full test suite**

Run: `uv run pytest -v`
Expected: All tests PASS (should be ~30 tests)

**Step 3: Commit**

```bash
git add tests/__init__.py tests/conftest.py
git commit -m "test: add test configuration and run full suite"
```

---

## Summary

**Total Tasks:** 11
**Total Tests:** ~31
**Commits:** 11

**Implementation order:**
1. Project setup (pyproject.toml, uv)
2. Config parsing with env var substitution
3. Authentication and authorization
4. Grist API client
5. Discovery tools (list_documents)
6. Read tools (list_tables, describe_table, get_records, sql_query)
7. Write tools (add_records, update_records, delete_records)
8. Schema tools (create_table, add_column, modify_column, delete_column)
9. MCP server entry point
10. Docker configuration
11. Final test verification
