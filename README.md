# grist-mcp

MCP server for AI agents to interact with Grist documents.

## Overview

grist-mcp is a [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) server that enables AI agents to read, write, and modify Grist spreadsheets. It provides secure, token-based access control with granular permissions per document.

## Features

- **Discovery**: List accessible documents with permissions
- **Read Operations**: List tables, describe columns, fetch records, run SQL queries
- **Write Operations**: Add, update, and delete records
- **Schema Operations**: Create tables, add/modify/delete columns
- **Security**: Token-based authentication with per-document permission scopes (read, write, schema)
- **Multi-tenant**: Support multiple Grist instances and documents

## Quick Start (Docker)

### Prerequisites

- Docker and Docker Compose
- Access to one or more Grist documents with API keys

### 1. Create configuration directory

```bash
mkdir grist-mcp && cd grist-mcp
```

### 2. Download configuration files

```bash
# Download docker-compose.yml
curl -O https://raw.githubusercontent.com/Xe138/grist-mcp-server/master/deploy/prod/docker-compose.yml

# Download example config
curl -O https://raw.githubusercontent.com/Xe138/grist-mcp-server/master/config.yaml.example
cp config.yaml.example config.yaml
```

### 3. Generate tokens

Generate a secure token for your agent:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
# or
openssl rand -base64 32
```

### 4. Configure config.yaml

Edit `config.yaml` to define your Grist documents and agent tokens:

```yaml
# Document definitions
documents:
  my-document:                           # Friendly name (used in token scopes)
    url: https://docs.getgrist.com       # Your Grist instance URL
    doc_id: abcd1234efgh5678             # Document ID from the URL
    api_key: your-grist-api-key          # Grist API key (or use ${ENV_VAR} syntax)

# Agent tokens with access scopes
tokens:
  - token: your-generated-token-here     # The token you generated in step 3
    name: my-agent                       # Human-readable name
    scope:
      - document: my-document            # Must match a document name above
        permissions: [read, write]       # Allowed: read, write, schema
```

**Finding your Grist document ID**: Open your Grist document in a browser. The URL will look like:
`https://docs.getgrist.com/abcd1234efgh5678/My-Document` - the document ID is `abcd1234efgh5678`.

**Getting a Grist API key**: In Grist, go to Profile Settings → API → Create API Key.

### 5. Create .env file

Create a `.env` file with your agent token:

```bash
# .env
GRIST_MCP_TOKEN=your-generated-token-here
PORT=3000
```

The `GRIST_MCP_TOKEN` must match one of the tokens defined in `config.yaml`.

### 6. Start the server

```bash
docker compose up -d
```

The server will be available at `http://localhost:3000`.

### 7. Configure your MCP client

Add to your MCP client configuration (e.g., Claude Desktop):

```json
{
  "mcpServers": {
    "grist": {
      "type": "sse",
      "url": "http://localhost:3000/sse"
    }
  }
}
```

## Available Tools

### Discovery
| Tool | Description |
|------|-------------|
| `list_documents` | List documents accessible to this agent with their permissions |

### Read Operations (requires `read` permission)
| Tool | Description |
|------|-------------|
| `list_tables` | List all tables in a document |
| `describe_table` | Get column information (id, type, formula) for a table |
| `get_records` | Fetch records with optional filter, sort, and limit |
| `sql_query` | Run a read-only SELECT query against a document |

### Write Operations (requires `write` permission)
| Tool | Description |
|------|-------------|
| `add_records` | Add new records to a table |
| `update_records` | Update existing records by ID |
| `delete_records` | Delete records by ID |

### Schema Operations (requires `schema` permission)
| Tool | Description |
|------|-------------|
| `create_table` | Create a new table with specified columns |
| `add_column` | Add a column to an existing table |
| `modify_column` | Change a column's type or formula |
| `delete_column` | Remove a column from a table |

## Configuration Reference

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `PORT` | Server port | `3000` |
| `GRIST_MCP_TOKEN` | Agent authentication token (required) | - |
| `CONFIG_PATH` | Path to config file inside container | `/app/config.yaml` |
| `LOG_LEVEL` | Logging verbosity (`DEBUG`, `INFO`, `WARNING`, `ERROR`) | `INFO` |

### config.yaml Structure

```yaml
# Document definitions (each is self-contained)
documents:
  budget-2024:
    url: https://work.getgrist.com
    doc_id: mK7xB2pQ9mN4v
    api_key: ${GRIST_WORK_API_KEY}      # Supports environment variable substitution

  personal-tracker:
    url: https://docs.getgrist.com
    doc_id: pN0zE5sT2qP7x
    api_key: ${GRIST_PERSONAL_API_KEY}

# Agent tokens with access scopes
tokens:
  - token: your-secure-token-here
    name: finance-agent
    scope:
      - document: budget-2024
        permissions: [read, write]       # Can read and write

  - token: another-token-here
    name: readonly-agent
    scope:
      - document: budget-2024
        permissions: [read]              # Read only
      - document: personal-tracker
        permissions: [read, write, schema]  # Full access
```

### Permission Levels

- `read`: Query tables and records, run SQL queries
- `write`: Add, update, delete records
- `schema`: Create tables, add/modify/delete columns

## Logging

### Configuration

Set the `LOG_LEVEL` environment variable to control logging verbosity:

| Level | Description |
|-------|-------------|
| `DEBUG` | Show all logs including HTTP requests and tool arguments |
| `INFO` | Show tool calls with stats (default) |
| `WARNING` | Show only auth errors and warnings |
| `ERROR` | Show only errors |

```bash
# In .env or docker-compose.yml
LOG_LEVEL=INFO
```

### Log Format

At `INFO` level, each tool call produces a single log line:

```
2026-01-02 10:15:23 | agent-name (abc...xyz) | get_records | sales | 42 records | success | 125ms
```

| Field | Description |
|-------|-------------|
| Timestamp | `YYYY-MM-DD HH:MM:SS` |
| Agent | Agent name with truncated token |
| Tool | MCP tool name |
| Document | Document name (or `-` for list_documents) |
| Stats | Operation result (e.g., `42 records`, `3 tables`) |
| Status | `success`, `auth_error`, or `error` |
| Duration | Execution time in milliseconds |

Errors include details on a second indented line:

```
2026-01-02 10:15:23 | agent-name (abc...xyz) | add_records | sales | - | error | 89ms
    Grist API error: Invalid column 'foo'
```

### Production Recommendations

- Use `LOG_LEVEL=INFO` for normal operation (default)
- Use `LOG_LEVEL=DEBUG` for troubleshooting (shows HTTP traffic)
- Use `LOG_LEVEL=WARNING` for minimal logging

## Security

- **Token-based auth**: Each agent has a unique token with specific document access
- **Permission scopes**: Granular control with `read`, `write`, and `schema` permissions
- **SQL validation**: Only SELECT queries allowed, no multi-statement queries
- **API key isolation**: Each document can use a different Grist API key
- **No token exposure**: Tokens are validated at startup, not stored in responses

## Development

### Requirements

- Python 3.14+
- uv package manager

### Local Setup

```bash
# Clone the repository
git clone https://github.com/Xe138/grist-mcp-server.git
cd grist-mcp-server

# Install dependencies
uv sync --dev

# Run tests
make test-unit
```

### Running Locally

```bash
export GRIST_MCP_TOKEN="your-agent-token"
CONFIG_PATH=./config.yaml uv run python -m grist_mcp.main
```

### Project Structure

```
grist-mcp/
├── src/grist_mcp/
│   ├── main.py          # Entry point
│   ├── server.py        # MCP server setup and tool registration
│   ├── config.py        # Configuration loading
│   ├── auth.py          # Authentication and authorization
│   ├── grist_client.py  # Grist API client
│   └── tools/
│       ├── discovery.py # list_documents
│       ├── read.py      # Read operations
│       ├── write.py     # Write operations
│       └── schema.py    # Schema operations
├── tests/
│   ├── unit/            # Unit tests
│   └── integration/     # Integration tests
├── deploy/
│   ├── dev/             # Development docker-compose
│   ├── test/            # Test docker-compose
│   └── prod/            # Production docker-compose
└── config.yaml.example
```

## License

MIT
