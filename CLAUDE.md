# CLAUDE.md

Project-specific instructions for Claude Code.

## Project Overview

grist-mcp is an MCP (Model Context Protocol) server that enables AI agents to interact with Grist spreadsheet documents. It provides secure, token-based access with granular permissions.

## Tech Stack

- Python 3.14+
- MCP SDK (`mcp` package)
- httpx for async HTTP requests
- PyYAML for configuration
- pytest + pytest-asyncio + pytest-httpx for testing

## Commands

```bash
# Run tests
uv run pytest -v

# Run a specific test file
uv run pytest tests/test_auth.py -v

# Run the server (requires config and token)
CONFIG_PATH=./config.yaml GRIST_MCP_TOKEN=your-token uv run python -m grist_mcp.main
```

## Project Structure

```
src/grist_mcp/
├── main.py          # Entry point, runs stdio server
├── server.py        # MCP server setup, tool registration, call_tool dispatch
├── config.py        # YAML config loading with env var substitution
├── auth.py          # Token auth and permission checking
├── grist_client.py  # Async Grist API client
└── tools/
    ├── discovery.py # list_documents tool
    ├── read.py      # list_tables, describe_table, get_records, sql_query
    ├── write.py     # add_records, update_records, delete_records
    └── schema.py    # create_table, add_column, modify_column, delete_column
```

## Key Patterns

### Authentication Flow
1. Token provided via `GRIST_MCP_TOKEN` env var or passed to `create_server()`
2. `Authenticator.authenticate()` validates token and returns `Agent` object
3. Each tool call uses `Authenticator.authorize()` to check document + permission

### Permission Levels
- `read`: Query tables and records
- `write`: Add, update, delete records
- `schema`: Create tables, modify columns

### Tool Implementation Pattern
All tools follow this pattern:
```python
async def tool_name(agent, auth, document, ..., client=None):
    auth.authorize(agent, document, Permission.X)
    if client is None:
        doc = auth.get_document(document)
        client = GristClient(doc)
    result = await client.some_method(...)
    return {"key": result}
```

The optional `client` parameter enables dependency injection for testing.

## Testing

Tests use pytest-httpx to mock Grist API responses. Each test file has fixtures for common setup:
- `test_auth.py`: Uses in-memory Config objects
- `test_grist_client.py`: Uses HTTPXMock for API mocking
- `test_tools_*.py`: Combine auth fixtures with mocked clients

## Configuration

See `config.yaml.example` for the configuration format. Key points:
- Documents define Grist instance URL, doc ID, and API key
- Tokens define agent access with document/permission scopes
- Environment variables can be used with `${VAR}` syntax
