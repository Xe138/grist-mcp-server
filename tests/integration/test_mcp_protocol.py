"""Test MCP protocol compliance over SSE transport."""

import os
from contextlib import asynccontextmanager

import pytest
from mcp import ClientSession
from mcp.client.sse import sse_client


GRIST_MCP_URL = os.environ.get("GRIST_MCP_URL", "http://localhost:3000")


@asynccontextmanager
async def create_mcp_session():
    """Create and yield an MCP session."""
    async with sse_client(f"{GRIST_MCP_URL}/sse") as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            yield session


@pytest.mark.asyncio
async def test_mcp_protocol_compliance(services_ready):
    """Test MCP protocol compliance - connection, tools, descriptions, schemas."""
    async with create_mcp_session() as client:
        # Test 1: Connection initializes
        assert client is not None

        # Test 2: list_tools returns all expected tools
        result = await client.list_tools()
        tool_names = [tool.name for tool in result.tools]

        expected_tools = [
            "list_documents",
            "list_tables",
            "describe_table",
            "get_records",
            "sql_query",
            "add_records",
            "update_records",
            "delete_records",
            "create_table",
            "add_column",
            "modify_column",
            "delete_column",
        ]

        for expected in expected_tools:
            assert expected in tool_names, f"Missing tool: {expected}"

        assert len(result.tools) == 12, f"Expected 12 tools, got {len(result.tools)}"

        # Test 3: All tools have descriptions
        for tool in result.tools:
            assert tool.description, f"Tool {tool.name} has no description"
            assert len(tool.description) > 10, f"Tool {tool.name} description too short"

        # Test 4: All tools have input schemas
        for tool in result.tools:
            assert tool.inputSchema is not None, f"Tool {tool.name} has no inputSchema"
            assert "type" in tool.inputSchema, f"Tool {tool.name} schema missing type"
