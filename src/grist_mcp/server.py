"""MCP server setup and tool registration."""

import json
import time

from mcp.server import Server
from mcp.types import Tool, TextContent

from grist_mcp.auth import Authenticator, Agent, AuthError
from grist_mcp.session import SessionTokenManager
from grist_mcp.tools.session import get_proxy_documentation as _get_proxy_documentation
from grist_mcp.tools.session import request_session_token as _request_session_token
from grist_mcp.logging import get_logger, extract_stats, format_tool_log

logger = get_logger("server")

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


def create_server(
    auth: Authenticator,
    agent: Agent,
    token_manager: SessionTokenManager | None = None,
    proxy_base_url: str | None = None,
) -> Server:
    """Create and configure the MCP server for an authenticated agent.

    Args:
        auth: Authenticator instance for permission checks.
        agent: The authenticated agent for this server instance.
        token_manager: Optional session token manager for HTTP proxy access.
        proxy_base_url: Base URL for the proxy endpoint (e.g., "https://example.com").

    Returns:
        Configured MCP Server instance.
    """
    server = Server("grist-mcp")
    _current_agent = agent
    _proxy_base_url = proxy_base_url

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
                        "label": {"type": "string", "description": "Display label for the column"},
                    },
                    "required": ["document", "table", "column_id", "column_type"],
                },
            ),
            Tool(
                name="modify_column",
                description="Modify a column's type, formula, or label",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "document": {"type": "string"},
                        "table": {"type": "string"},
                        "column_id": {"type": "string"},
                        "type": {"type": "string"},
                        "formula": {"type": "string"},
                        "label": {"type": "string", "description": "Display label for the column"},
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
        ]

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
                    label=arguments.get("label"),
                )
            elif name == "modify_column":
                result = await _modify_column(
                    _current_agent, auth, arguments["document"], arguments["table"],
                    arguments["column_id"],
                    type=arguments.get("type"),
                    formula=arguments.get("formula"),
                    label=arguments.get("label"),
                )
            elif name == "delete_column":
                result = await _delete_column(
                    _current_agent, auth, arguments["document"], arguments["table"],
                    arguments["column_id"],
                )
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
                    proxy_base_url=_proxy_base_url,
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

    return server
