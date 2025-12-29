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

## Requirements

- Python 3.14+
- Access to one or more Grist documents with API keys

## Installation

```bash
# Clone the repository
git clone https://github.com/your-org/grist-mcp.git
cd grist-mcp

# Install with uv
uv sync --dev
```

## Configuration

Create a `config.yaml` file based on the example:

```bash
cp config.yaml.example config.yaml
```

### Configuration Structure

```yaml
# Document definitions
documents:
  my-document:
    url: https://docs.getgrist.com      # Grist instance URL
    doc_id: abcd1234                     # Document ID from URL
    api_key: ${GRIST_API_KEY}            # API key (supports env vars)

# Agent tokens with access scopes
tokens:
  - token: your-secret-token             # Unique token for this agent
    name: my-agent                       # Human-readable name
    scope:
      - document: my-document
        permissions: [read, write]       # Allowed: read, write, schema
```

### Generating Tokens

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
# or
openssl rand -base64 32
```

### Environment Variables

- `CONFIG_PATH`: Path to config file (default: `/app/config.yaml`)
- `GRIST_MCP_TOKEN`: Agent token for authentication
- Config file supports `${VAR}` syntax for API keys

## Usage

### Running the Server

```bash
# Set your agent token
export GRIST_MCP_TOKEN="your-agent-token"

# Run with custom config path
CONFIG_PATH=./config.yaml uv run python -m grist_mcp.main
```

### MCP Client Configuration

Add to your MCP client configuration (e.g., Claude Desktop):

```json
{
  "mcpServers": {
    "grist": {
      "command": "uv",
      "args": ["run", "python", "-m", "grist_mcp.main"],
      "cwd": "/path/to/grist-mcp",
      "env": {
        "CONFIG_PATH": "/path/to/config.yaml",
        "GRIST_MCP_TOKEN": "your-agent-token",
        "GRIST_API_KEY": "your-grist-api-key"
      }
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

## Security

- **Token-based auth**: Each agent has a unique token with specific document access
- **Permission scopes**: Granular control with `read`, `write`, and `schema` permissions
- **SQL validation**: Only SELECT queries allowed, no multi-statement queries
- **API key isolation**: Each document can use a different Grist API key
- **No token exposure**: Tokens are validated at startup, not stored in responses

## Development

### Running Tests

```bash
uv run pytest -v
```

### Project Structure

```
grist-mcp/
├── src/grist_mcp/
│   ├── __init__.py
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
├── config.yaml.example
└── pyproject.toml
```

## License

MIT
