# Logging Improvements Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add informative application-level logging that shows agent identity, tool usage, document access, and operation stats.

**Architecture:** New `logging.py` module provides setup and formatting. `server.py` wraps tool calls with timing and stats extraction. `main.py` initializes logging and configures uvicorn to suppress health check noise.

**Tech Stack:** Python `logging` stdlib, custom `Formatter`, uvicorn log config

---

### Task 1: Token Truncation Helper

**Files:**
- Create: `src/grist_mcp/logging.py`
- Test: `tests/unit/test_logging.py`

**Step 1: Write the failing test**

Create `tests/unit/test_logging.py`:

```python
"""Unit tests for logging module."""

import pytest

from grist_mcp.logging import truncate_token


class TestTruncateToken:
    def test_normal_token_shows_prefix_suffix(self):
        token = "abcdefghijklmnop"
        assert truncate_token(token) == "abc...nop"

    def test_short_token_shows_asterisks(self):
        token = "abcdefgh"  # 8 chars
        assert truncate_token(token) == "***"

    def test_very_short_token_shows_asterisks(self):
        token = "abc"
        assert truncate_token(token) == "***"
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_logging.py -v`
Expected: FAIL with "No module named 'grist_mcp.logging'"

**Step 3: Write minimal implementation**

Create `src/grist_mcp/logging.py`:

```python
"""Logging configuration and utilities."""


def truncate_token(token: str) -> str:
    """Truncate token to show first 3 and last 3 chars.

    Tokens 8 chars or shorter show *** for security.
    """
    if len(token) <= 8:
        return "***"
    return f"{token[:3]}...{token[-3:]}"
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_logging.py -v`
Expected: PASS (3 tests)

**Step 5: Commit**

```bash
git add src/grist_mcp/logging.py tests/unit/test_logging.py
git commit -m "feat(logging): add token truncation helper"
```

---

### Task 2: Stats Extraction Function

**Files:**
- Modify: `src/grist_mcp/logging.py`
- Modify: `tests/unit/test_logging.py`

**Step 1: Write the failing tests**

Add to `tests/unit/test_logging.py`:

```python
from grist_mcp.logging import truncate_token, extract_stats


class TestExtractStats:
    def test_list_documents(self):
        result = {"documents": [{"name": "a"}, {"name": "b"}, {"name": "c"}]}
        assert extract_stats("list_documents", {}, result) == "3 docs"

    def test_list_tables(self):
        result = {"tables": ["Orders", "Products"]}
        assert extract_stats("list_tables", {}, result) == "2 tables"

    def test_describe_table(self):
        result = {"columns": [{"id": "A"}, {"id": "B"}]}
        assert extract_stats("describe_table", {}, result) == "2 columns"

    def test_get_records(self):
        result = {"records": [{"id": 1}, {"id": 2}]}
        assert extract_stats("get_records", {}, result) == "2 records"

    def test_sql_query(self):
        result = {"records": [{"a": 1}, {"a": 2}, {"a": 3}]}
        assert extract_stats("sql_query", {}, result) == "3 rows"

    def test_add_records_from_args(self):
        args = {"records": [{"a": 1}, {"a": 2}]}
        assert extract_stats("add_records", args, {"ids": [1, 2]}) == "2 records"

    def test_update_records_from_args(self):
        args = {"records": [{"id": 1, "fields": {}}, {"id": 2, "fields": {}}]}
        assert extract_stats("update_records", args, {}) == "2 records"

    def test_delete_records_from_args(self):
        args = {"record_ids": [1, 2, 3]}
        assert extract_stats("delete_records", args, {}) == "3 records"

    def test_create_table(self):
        args = {"columns": [{"id": "A"}, {"id": "B"}]}
        assert extract_stats("create_table", args, {}) == "2 columns"

    def test_single_column_ops(self):
        assert extract_stats("add_column", {}, {}) == "1 column"
        assert extract_stats("modify_column", {}, {}) == "1 column"
        assert extract_stats("delete_column", {}, {}) == "1 column"

    def test_unknown_tool(self):
        assert extract_stats("unknown_tool", {}, {}) == "-"
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_logging.py::TestExtractStats -v`
Expected: FAIL with "cannot import name 'extract_stats'"

**Step 3: Write minimal implementation**

Add to `src/grist_mcp/logging.py`:

```python
def extract_stats(tool_name: str, arguments: dict, result: dict) -> str:
    """Extract meaningful stats from tool call based on tool type."""
    if tool_name == "list_documents":
        count = len(result.get("documents", []))
        return f"{count} docs"

    if tool_name == "list_tables":
        count = len(result.get("tables", []))
        return f"{count} tables"

    if tool_name == "describe_table":
        count = len(result.get("columns", []))
        return f"{count} columns"

    if tool_name == "get_records":
        count = len(result.get("records", []))
        return f"{count} records"

    if tool_name == "sql_query":
        count = len(result.get("records", []))
        return f"{count} rows"

    if tool_name == "add_records":
        count = len(arguments.get("records", []))
        return f"{count} records"

    if tool_name == "update_records":
        count = len(arguments.get("records", []))
        return f"{count} records"

    if tool_name == "delete_records":
        count = len(arguments.get("record_ids", []))
        return f"{count} records"

    if tool_name == "create_table":
        count = len(arguments.get("columns", []))
        return f"{count} columns"

    if tool_name in ("add_column", "modify_column", "delete_column"):
        return "1 column"

    return "-"
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_logging.py -v`
Expected: PASS (all tests)

**Step 5: Commit**

```bash
git add src/grist_mcp/logging.py tests/unit/test_logging.py
git commit -m "feat(logging): add stats extraction for all tools"
```

---

### Task 3: Log Line Formatter

**Files:**
- Modify: `src/grist_mcp/logging.py`
- Modify: `tests/unit/test_logging.py`

**Step 1: Write the failing tests**

Add to `tests/unit/test_logging.py`:

```python
from grist_mcp.logging import truncate_token, extract_stats, format_tool_log


class TestFormatToolLog:
    def test_success_format(self):
        line = format_tool_log(
            agent_name="dev-agent",
            token="abcdefghijklmnop",
            tool="get_records",
            document="sales",
            stats="42 records",
            status="success",
            duration_ms=125,
        )
        assert "dev-agent" in line
        assert "abc...nop" in line
        assert "get_records" in line
        assert "sales" in line
        assert "42 records" in line
        assert "success" in line
        assert "125ms" in line
        # Check pipe-delimited format
        assert line.count("|") == 6

    def test_no_document(self):
        line = format_tool_log(
            agent_name="dev-agent",
            token="abcdefghijklmnop",
            tool="list_documents",
            document=None,
            stats="3 docs",
            status="success",
            duration_ms=45,
        )
        assert "| - |" in line

    def test_error_format(self):
        line = format_tool_log(
            agent_name="dev-agent",
            token="abcdefghijklmnop",
            tool="add_records",
            document="inventory",
            stats="5 records",
            status="error",
            duration_ms=89,
            error_message="Grist API error: Invalid column 'foo'",
        )
        assert "error" in line
        assert "\n    Grist API error: Invalid column 'foo'" in line
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_logging.py::TestFormatToolLog -v`
Expected: FAIL with "cannot import name 'format_tool_log'"

**Step 3: Write minimal implementation**

Add to `src/grist_mcp/logging.py`:

```python
from datetime import datetime


def format_tool_log(
    agent_name: str,
    token: str,
    tool: str,
    document: str | None,
    stats: str,
    status: str,
    duration_ms: int,
    error_message: str | None = None,
) -> str:
    """Format a tool call log line.

    Format: YYYY-MM-DD HH:MM:SS | agent (token) | tool | doc | stats | status | duration
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    truncated = truncate_token(token)
    doc = document if document else "-"

    line = f"{timestamp} | {agent_name} ({truncated}) | {tool} | {doc} | {stats} | {status} | {duration_ms}ms"

    if error_message:
        line += f"\n    {error_message}"

    return line
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_logging.py -v`
Expected: PASS (all tests)

**Step 5: Commit**

```bash
git add src/grist_mcp/logging.py tests/unit/test_logging.py
git commit -m "feat(logging): add log line formatter"
```

---

### Task 4: Setup Logging Function

**Files:**
- Modify: `src/grist_mcp/logging.py`
- Modify: `tests/unit/test_logging.py`

**Step 1: Write the failing tests**

Add to `tests/unit/test_logging.py`:

```python
import logging
import os


class TestSetupLogging:
    def test_default_level_is_info(self, monkeypatch):
        monkeypatch.delenv("LOG_LEVEL", raising=False)

        from grist_mcp.logging import setup_logging
        setup_logging()

        logger = logging.getLogger("grist_mcp")
        assert logger.level == logging.INFO

    def test_respects_log_level_env(self, monkeypatch):
        monkeypatch.setenv("LOG_LEVEL", "DEBUG")

        from grist_mcp.logging import setup_logging
        setup_logging()

        logger = logging.getLogger("grist_mcp")
        assert logger.level == logging.DEBUG

    def test_invalid_level_defaults_to_info(self, monkeypatch):
        monkeypatch.setenv("LOG_LEVEL", "INVALID")

        from grist_mcp.logging import setup_logging
        setup_logging()

        logger = logging.getLogger("grist_mcp")
        assert logger.level == logging.INFO
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_logging.py::TestSetupLogging -v`
Expected: FAIL with "cannot import name 'setup_logging'"

**Step 3: Write minimal implementation**

Add to `src/grist_mcp/logging.py`:

```python
import logging
import os


def setup_logging() -> None:
    """Configure logging based on LOG_LEVEL environment variable.

    Valid levels: DEBUG, INFO, WARNING, ERROR (default: INFO)
    """
    level_name = os.environ.get("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, None)

    if not isinstance(level, int):
        level = logging.INFO

    logger = logging.getLogger("grist_mcp")
    logger.setLevel(level)

    # Only add handler if not already configured
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_logging.py -v`
Expected: PASS (all tests)

**Step 5: Commit**

```bash
git add src/grist_mcp/logging.py tests/unit/test_logging.py
git commit -m "feat(logging): add setup_logging with LOG_LEVEL support"
```

---

### Task 5: Get Logger Helper

**Files:**
- Modify: `src/grist_mcp/logging.py`
- Modify: `tests/unit/test_logging.py`

**Step 1: Write the failing test**

Add to `tests/unit/test_logging.py`:

```python
class TestGetLogger:
    def test_returns_child_logger(self):
        from grist_mcp.logging import get_logger

        logger = get_logger("server")
        assert logger.name == "grist_mcp.server"

    def test_inherits_parent_level(self, monkeypatch):
        monkeypatch.setenv("LOG_LEVEL", "WARNING")

        from grist_mcp.logging import setup_logging, get_logger
        setup_logging()

        logger = get_logger("test")
        # Child inherits from parent when level is NOTSET
        assert logger.getEffectiveLevel() == logging.WARNING
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_logging.py::TestGetLogger -v`
Expected: FAIL with "cannot import name 'get_logger'"

**Step 3: Write minimal implementation**

Add to `src/grist_mcp/logging.py`:

```python
def get_logger(name: str) -> logging.Logger:
    """Get a child logger under the grist_mcp namespace."""
    return logging.getLogger(f"grist_mcp.{name}")
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_logging.py -v`
Expected: PASS (all tests)

**Step 5: Commit**

```bash
git add src/grist_mcp/logging.py tests/unit/test_logging.py
git commit -m "feat(logging): add get_logger helper"
```

---

### Task 6: Integrate Logging into Server

**Files:**
- Modify: `src/grist_mcp/server.py`

**Step 1: Add logging imports and logger**

At the top of `src/grist_mcp/server.py`, add imports:

```python
import time
from grist_mcp.logging import get_logger, extract_stats, format_tool_log

logger = get_logger("server")
```

**Step 2: Wrap call_tool with logging**

Replace the `call_tool` function body (lines 209-276) with this logged version:

```python
    @server.call_tool()
    async def call_tool(name: str, arguments: dict) -> list[TextContent]:
        start_time = time.time()
        document = arguments.get("document")

        # Log arguments at DEBUG level
        logger.debug(
            format_tool_log(
                agent_name=_current_agent.name,
                token=_current_agent.token,
                tool=name,
                document=document,
                stats=f"args: {json.dumps(arguments)}",
                status="started",
                duration_ms=0,
            )
        )

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

            duration_ms = int((time.time() - start_time) * 1000)
            stats = extract_stats(name, arguments, result)

            logger.info(
                format_tool_log(
                    agent_name=_current_agent.name,
                    token=_current_agent.token,
                    tool=name,
                    document=document,
                    stats=stats,
                    status="success",
                    duration_ms=duration_ms,
                )
            )

            return [TextContent(type="text", text=json.dumps(result))]

        except AuthError as e:
            duration_ms = int((time.time() - start_time) * 1000)
            logger.warning(
                format_tool_log(
                    agent_name=_current_agent.name,
                    token=_current_agent.token,
                    tool=name,
                    document=document,
                    stats="-",
                    status="auth_error",
                    duration_ms=duration_ms,
                    error_message=str(e),
                )
            )
            return [TextContent(type="text", text=f"Authorization error: {e}")]

        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            logger.error(
                format_tool_log(
                    agent_name=_current_agent.name,
                    token=_current_agent.token,
                    tool=name,
                    document=document,
                    stats="-",
                    status="error",
                    duration_ms=duration_ms,
                    error_message=str(e),
                )
            )
            return [TextContent(type="text", text=f"Error: {e}")]
```

**Step 3: Run tests to verify nothing broke**

Run: `uv run pytest tests/unit/ -v`
Expected: PASS (all tests)

**Step 4: Commit**

```bash
git add src/grist_mcp/server.py
git commit -m "feat(logging): add tool call logging to server"
```

---

### Task 7: Initialize Logging in Main

**Files:**
- Modify: `src/grist_mcp/main.py`

**Step 1: Add logging setup to main()**

Add import at top of `src/grist_mcp/main.py`:

```python
from grist_mcp.logging import setup_logging
```

**Step 2: Call setup_logging at start of main()**

In the `main()` function, add as the first line after the port/config variables:

```python
def main():
    """Run the SSE server."""
    port = int(os.environ.get("PORT", "3000"))
    external_port = int(os.environ.get("EXTERNAL_PORT", str(port)))
    config_path = os.environ.get("CONFIG_PATH", "/app/config.yaml")

    setup_logging()  # <-- Add this line

    if not _ensure_config(config_path):
```

**Step 3: Run tests to verify nothing broke**

Run: `uv run pytest tests/unit/ -v`
Expected: PASS (all tests)

**Step 4: Commit**

```bash
git add src/grist_mcp/main.py
git commit -m "feat(logging): initialize logging on server startup"
```

---

### Task 8: Suppress Health Check Noise

**Files:**
- Modify: `src/grist_mcp/main.py`

**Step 1: Configure uvicorn to use custom log config**

Replace the `uvicorn.run` call in `main()` with:

```python
    # Configure uvicorn logging to reduce health check noise
    log_config = uvicorn.config.LOGGING_CONFIG
    log_config["formatters"]["default"]["fmt"] = "%(message)s"
    log_config["formatters"]["access"]["fmt"] = "%(message)s"

    uvicorn.run(app, host="0.0.0.0", port=port, log_config=log_config)
```

**Step 2: Add health check filter**

Create a filter class and apply it. Add before the `main()` function:

```python
class HealthCheckFilter(logging.Filter):
    """Filter out health check requests at INFO level."""

    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        if "/health" in message:
            # Downgrade to DEBUG by changing the level
            record.levelno = logging.DEBUG
            record.levelname = "DEBUG"
        return True
```

Add import at top:

```python
import logging
```

**Step 3: Apply filter in main()**

After `setup_logging()` call, add:

```python
    setup_logging()

    # Add health check filter to uvicorn access logger
    logging.getLogger("uvicorn.access").addFilter(HealthCheckFilter())
```

**Step 4: Run tests to verify nothing broke**

Run: `uv run pytest tests/unit/ -v`
Expected: PASS (all tests)

**Step 5: Commit**

```bash
git add src/grist_mcp/main.py
git commit -m "feat(logging): suppress health checks at INFO level"
```

---

### Task 9: Manual Verification

**Step 1: Start development environment**

Run: `make dev-up`

**Step 2: Make some tool calls**

Use Claude Code or another MCP client to call some tools (list_documents, get_records, etc.)

**Step 3: Verify log format**

Check docker logs show the expected format:
```
2026-01-02 10:15:23 | dev-agent (abc...xyz) | get_records | sales | 42 records | success | 125ms
```

**Step 4: Test DEBUG level**

Restart with `LOG_LEVEL=DEBUG` and verify:
- Health checks appear
- Detailed args appear for each call

**Step 5: Clean up**

Run: `make dev-down`

---

### Task 10: Update Module Exports

**Files:**
- Modify: `src/grist_mcp/logging.py`

**Step 1: Add __all__ export list**

At the top of `src/grist_mcp/logging.py` (after imports), add:

```python
__all__ = [
    "setup_logging",
    "get_logger",
    "truncate_token",
    "extract_stats",
    "format_tool_log",
]
```

**Step 2: Run all tests**

Run: `uv run pytest tests/unit/ -v`
Expected: PASS (all tests)

**Step 3: Final commit**

```bash
git add src/grist_mcp/logging.py
git commit -m "chore(logging): add module exports"
```

---

## Summary

After completing all tasks, the logging module provides:
- `LOG_LEVEL` environment variable support (DEBUG/INFO/WARNING/ERROR)
- Human-readable pipe-delimited log format
- Token truncation for security
- Stats extraction per tool type
- Health check suppression at INFO level
- Multi-line error details

The implementation follows TDD with frequent commits, keeping each change small and verifiable.
