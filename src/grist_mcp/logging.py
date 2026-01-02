"""Logging configuration and utilities."""

import logging
import os
from datetime import datetime

__all__ = [
    "setup_logging",
    "get_logger",
    "truncate_token",
    "extract_stats",
    "format_tool_log",
]


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
    logger.propagate = False  # Prevent duplicate logs to root logger

    # Only add handler if not already configured
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)


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


def truncate_token(token: str) -> str:
    """Truncate token to show first 3 and last 3 chars.

    Tokens 8 chars or shorter show *** for security.
    """
    if len(token) <= 8:
        return "***"
    return f"{token[:3]}...{token[-3:]}"


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


def get_logger(name: str) -> logging.Logger:
    """Get a child logger under the grist_mcp namespace."""
    return logging.getLogger(f"grist_mcp.{name}")
