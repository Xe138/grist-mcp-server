# Logging Improvements Design

## Overview

Improve MCP server logging to provide meaningful operational visibility. Replace generic HTTP request logs with application-level context including agent identity, tool usage, document access, and operation stats.

## Current State

Logs show only uvicorn HTTP requests with no application context:
```
INFO:     172.20.0.2:43254 - "POST /messages?session_id=... HTTP/1.1" 202 Accepted
INFO:     127.0.0.1:41508 - "GET /health HTTP/1.1" 200 OK
```

## Desired State

Human-readable single-line format with full context:
```
2025-01-02 10:15:23 | dev-agent (abc...xyz) | get_records | sales | 42 records | success | 125ms
2025-01-02 10:15:24 | dev-agent (abc...xyz) | update_records | sales | 3 records | success | 89ms
2025-01-02 10:15:25 | dev-agent (abc...xyz) | add_records | inventory | 5 records | error | 89ms
    Grist API error: Invalid column 'foo'
```

## Design Decisions

| Decision | Choice |
|----------|--------|
| Log format | Human-readable single-line (pipe-delimited) |
| Configuration | Environment variable only (`LOG_LEVEL`) |
| Log levels | Standard (DEBUG/INFO/WARNING/ERROR) |
| Health checks | DEBUG level only (suppressed at INFO) |
| Error details | Multi-line (indented on second line) |

## Log Format

```
YYYY-MM-DD HH:MM:SS | <agent_name> (<token_truncated>) | <tool> | <document> | <stats> | <status> | <duration>
```

**Token truncation:** First 3 and last 3 characters (e.g., `abc...xyz`). Tokens <=8 chars show `***`.

**Document field:** Shows `-` for tools without a document (e.g., `list_documents`).

## Log Levels

| Level | Events |
|-------|--------|
| ERROR | Unhandled exceptions, Grist API failures |
| WARNING | Auth errors (invalid token, permission denied) |
| INFO | Tool calls (one line per call with stats) |
| DEBUG | Health checks, detailed arguments, full results |

**Environment variable:** `LOG_LEVEL` (default: `INFO`)

## Stats Per Tool

| Tool | Stats |
|------|-------|
| `list_documents` | `N docs` |
| `list_tables` | `N tables` |
| `describe_table` | `N columns` |
| `get_records` | `N records` |
| `sql_query` | `N rows` |
| `add_records` | `N records` |
| `update_records` | `N records` |
| `delete_records` | `N records` |
| `create_table` | `N columns` |
| `add_column` | `1 column` |
| `modify_column` | `1 column` |
| `delete_column` | `1 column` |

## Files Changed

| File | Change |
|------|--------|
| `src/grist_mcp/logging.py` | New - logging setup, formatters, stats extraction |
| `src/grist_mcp/main.py` | Call `setup_logging()`, configure uvicorn logger |
| `src/grist_mcp/server.py` | Wrap `call_tool` with logging |
| `tests/unit/test_logging.py` | New - unit tests for logging module |

Tool implementations in `tools/` remain unchanged - logging is handled at the server layer.

## Testing

**Unit tests:**
- `test_setup_logging_default_level`
- `test_setup_logging_from_env`
- `test_token_truncation`
- `test_extract_stats`
- `test_format_log_line`
- `test_error_multiline_format`

**Manual verification:**
- Run `make dev-up`, make tool calls, verify log format
- Test with `LOG_LEVEL=DEBUG` for verbose output
