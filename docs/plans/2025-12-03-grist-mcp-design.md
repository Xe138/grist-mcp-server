# Grist MCP Server Design

## Overview

A dockerized MCP server that allows AI agents to interact with Grist documents. Each agent authenticates with a token that grants access to specific documents with defined permission levels.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    grist-mcp Container                       │
│                                                              │
│  ┌──────────────────────┐          ┌──────────────────────┐ │
│  │     MCP Server       │          │    Grist Client      │ │
│  │     (SSE/HTTP)       │─────────▶│       Layer          │ │
│  │      :8080           │          │                      │ │
│  └──────────┬───────────┘          └──────────────────────┘ │
│             │                                                │
│     ┌───────▼───────┐                                       │
│     │  config.yaml  │ ← Mounted volume (read-only)          │
│     └───────────────┘                                       │
└─────────────────────────────────────────────────────────────┘
          │                              │
          ▼                              ▼
   ┌─────────────┐               ┌─────────────────┐
   │ AI Agents   │               │  Grist Servers  │
   │ (with tokens)│               │                 │
   └─────────────┘               └─────────────────┘
```

**Key characteristics:**
- Single container, single port (8080)
- All configuration from one YAML file
- No database, no admin API
- Restart container to apply config changes

## Configuration

### config.yaml

```yaml
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
  - token: dG9rZW4tZmluYW5jZS1hZ2VudC0xMjM0NTY3ODkw
    name: finance-agent
    scope:
      - document: budget-2024
        permissions: [read, write]
      - document: expenses
        permissions: [read]

  - token: K7xB2pQ9mN4vR8wY1zA3cE6fH0jL5oI2sU7tD4gM
    name: analytics-agent
    scope:
      - document: personal-tracker
        permissions: [read, write, schema]
```

### Permission Levels

| Permission | Description |
|------------|-------------|
| `read` | Query tables, get records, list structure |
| `write` | Create, update, delete records |
| `schema` | Create/modify tables, columns, formulas |

### Environment Variables

API keys are referenced via `${VAR}` syntax in config.yaml and resolved at startup. Store actual keys in `.env` file:

```bash
GRIST_WORK_API_KEY=actual-api-key-here
GRIST_PERSONAL_API_KEY=another-api-key
```

## MCP Tools

### Discovery

| Tool | Permission | Description |
|------|------------|-------------|
| `list_documents` | (always available) | List documents this token can access with their permissions |

### Read Operations (requires `read`)

| Tool | Description |
|------|-------------|
| `list_tables` | List all tables in a document |
| `describe_table` | Get column names, types, and formulas for a table |
| `get_records` | Fetch records with optional filters and sorting |
| `sql_query` | Run read-only SQL against the document |

### Write Operations (requires `write`)

| Tool | Description |
|------|-------------|
| `add_records` | Insert one or more records into a table |
| `update_records` | Update existing records by ID |
| `delete_records` | Delete records by ID |

### Schema Operations (requires `schema`)

| Tool | Description |
|------|-------------|
| `create_table` | Create a new table with column definitions |
| `add_column` | Add a column to an existing table |
| `modify_column` | Change column type or formula |
| `delete_column` | Remove a column from a table |

## Authentication Flow

1. Agent connects to MCP server at `http://host:8080/mcp`
2. Agent provides token via `Authorization: Bearer <token>` header
3. Server looks up token in config, retrieves associated scope
4. All subsequent tool calls are validated against that scope

### Validation on Each Tool Call

```
Agent calls: get_records(document="budget-2024", table="Transactions")
                              │
                              ▼
              ┌───────────────────────────────┐
              │ 1. Is token valid?            │──No──▶ 401 Unauthorized
              └───────────────┬───────────────┘
                              │ Yes
                              ▼
              ┌───────────────────────────────┐
              │ 2. Does token have access to  │──No──▶ 403 Forbidden
              │    document "budget-2024"?    │
              └───────────────┬───────────────┘
                              │ Yes
                              ▼
              ┌───────────────────────────────┐
              │ 3. Does token have "read"     │──No──▶ 403 Forbidden
              │    permission on this doc?    │
              └───────────────┬───────────────┘
                              │ Yes
                              ▼
              ┌───────────────────────────────┐
              │ 4. Execute against Grist API  │
              │    using doc's api_key        │
              └───────────────────────────────┘
```

### Error Responses

- Invalid/missing token → `401 Unauthorized` (no details)
- Valid token, wrong document → `403 Forbidden: Document not in scope`
- Valid token, wrong permission → `403 Forbidden: Permission denied`

## Project Structure

```
grist-mcp/
├── Dockerfile
├── docker-compose.yaml
├── config.yaml.example      # Template with dummy values
├── pyproject.toml
├── uv.lock
├── src/
│   └── grist_mcp/
│       ├── __init__.py
│       ├── main.py          # Entry point, loads config, starts server
│       ├── config.py        # Config parsing, env var substitution
│       ├── auth.py          # Token validation, permission checking
│       ├── grist_client.py  # Grist API wrapper
│       └── tools/
│           ├── __init__.py
│           ├── discovery.py # list_documents
│           ├── read.py      # list_tables, describe_table, get_records, sql_query
│           ├── write.py     # add_records, update_records, delete_records
│           └── schema.py    # create_table, add_column, modify_column, delete_column
└── tests/
    └── ...
```

## Docker Setup

### docker-compose.yaml

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
```

### Dockerfile

```dockerfile
FROM ghcr.io/astral-sh/uv:python3.14-bookworm-slim
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev
COPY src/ ./src/
CMD ["uv", "run", "python", "-m", "grist_mcp.main"]
```

### pyproject.toml

```toml
[project]
name = "grist-mcp"
version = "0.1.0"
requires-python = ">=3.14"
dependencies = [
    "mcp",
    "httpx",
    "pyyaml",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

## Technology Stack

| Component | Choice |
|-----------|--------|
| Language | Python 3.14 |
| Package Manager | uv |
| MCP Framework | mcp (official SDK) |
| HTTP Client | httpx |
| Config Parsing | pyyaml |
| Deployment | Docker |
