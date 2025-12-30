"""Test MCP protocol compliance over SSE transport."""

import pytest


@pytest.mark.asyncio
async def test_mcp_connection_initializes(mcp_client):
    """Test that MCP client can connect and initialize."""
    # If we get here, connection and initialization succeeded
    assert mcp_client is not None


@pytest.mark.asyncio
async def test_list_tools_returns_all_tools(mcp_client):
    """Test that list_tools returns all expected tools."""
    result = await mcp_client.list_tools()
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

    assert len(result.tools) == 12


@pytest.mark.asyncio
async def test_list_tools_has_descriptions(mcp_client):
    """Test that all tools have descriptions."""
    result = await mcp_client.list_tools()

    for tool in result.tools:
        assert tool.description, f"Tool {tool.name} has no description"
        assert len(tool.description) > 10, f"Tool {tool.name} description too short"


@pytest.mark.asyncio
async def test_list_tools_has_input_schemas(mcp_client):
    """Test that all tools have input schemas."""
    result = await mcp_client.list_tools()

    for tool in result.tools:
        assert tool.inputSchema is not None, f"Tool {tool.name} has no inputSchema"
        assert "type" in tool.inputSchema, f"Tool {tool.name} schema missing type"
