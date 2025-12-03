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
