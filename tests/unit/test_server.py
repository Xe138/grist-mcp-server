import pytest
from mcp.types import ListToolsRequest
from grist_mcp.server import create_server


@pytest.mark.asyncio
async def test_create_server_registers_tools(tmp_path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text("""
documents:
  test-doc:
    url: https://grist.example.com
    doc_id: abc123
    api_key: test-key

tokens:
  - token: test-token
    name: test-agent
    scope:
      - document: test-doc
        permissions: [read, write, schema]
""")

    server = create_server(str(config_file), token="test-token")

    # Server should have tools registered
    assert server is not None

    # Get the list_tools handler and call it
    handler = server.request_handlers.get(ListToolsRequest)
    assert handler is not None

    req = ListToolsRequest(method="tools/list")
    result = await handler(req)

    # Check tool names are registered
    tool_names = [t.name for t in result.root.tools]
    assert "list_documents" in tool_names
    assert "list_tables" in tool_names
    assert "describe_table" in tool_names
    assert "get_records" in tool_names
    assert "sql_query" in tool_names
    assert "add_records" in tool_names
    assert "update_records" in tool_names
    assert "delete_records" in tool_names
    assert "create_table" in tool_names
    assert "add_column" in tool_names
    assert "modify_column" in tool_names
    assert "delete_column" in tool_names

    # Should have all 12 tools
    assert len(result.root.tools) == 12
