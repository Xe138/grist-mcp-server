"""Test tool calls through MCP client to verify Grist API interactions."""

import json
import os
from contextlib import asynccontextmanager

import httpx
import pytest
from mcp import ClientSession
from mcp.client.sse import sse_client


GRIST_MCP_URL = os.environ.get("GRIST_MCP_URL", "http://localhost:3000")
MOCK_GRIST_URL = os.environ.get("MOCK_GRIST_URL", "http://localhost:8484")


@asynccontextmanager
async def create_mcp_session():
    """Create and yield an MCP session."""
    async with sse_client(f"{GRIST_MCP_URL}/sse") as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            yield session


def get_mock_request_log():
    """Get the request log from mock Grist server."""
    with httpx.Client(base_url=MOCK_GRIST_URL, timeout=10.0) as client:
        return client.get("/_test/requests").json()


def clear_mock_request_log():
    """Clear the mock Grist request log."""
    with httpx.Client(base_url=MOCK_GRIST_URL, timeout=10.0) as client:
        client.post("/_test/requests/clear")


@pytest.mark.asyncio
async def test_all_tools(services_ready):
    """Test all MCP tools - reads, writes, schema ops, and auth errors."""
    async with create_mcp_session() as client:
        # ===== READ TOOLS =====

        # Test list_documents
        clear_mock_request_log()
        result = await client.call_tool("list_documents", {})
        assert len(result.content) == 1
        data = json.loads(result.content[0].text)
        assert "documents" in data
        assert len(data["documents"]) == 1
        assert data["documents"][0]["name"] == "test-doc"
        assert "read" in data["documents"][0]["permissions"]

        # Test list_tables
        clear_mock_request_log()
        result = await client.call_tool("list_tables", {"document": "test-doc"})
        data = json.loads(result.content[0].text)
        assert "tables" in data
        assert "People" in data["tables"]
        assert "Tasks" in data["tables"]
        log = get_mock_request_log()
        assert any("/tables" in entry["path"] for entry in log)

        # Test describe_table
        clear_mock_request_log()
        result = await client.call_tool(
            "describe_table",
            {"document": "test-doc", "table": "People"}
        )
        data = json.loads(result.content[0].text)
        assert "columns" in data
        column_ids = [c["id"] for c in data["columns"]]
        assert "Name" in column_ids
        assert "Age" in column_ids
        log = get_mock_request_log()
        assert any("/columns" in entry["path"] for entry in log)

        # Test get_records
        clear_mock_request_log()
        result = await client.call_tool(
            "get_records",
            {"document": "test-doc", "table": "People"}
        )
        data = json.loads(result.content[0].text)
        assert "records" in data
        assert len(data["records"]) == 2
        assert data["records"][0]["Name"] == "Alice"
        log = get_mock_request_log()
        assert any("/records" in entry["path"] and entry["method"] == "GET" for entry in log)

        # Test sql_query
        clear_mock_request_log()
        result = await client.call_tool(
            "sql_query",
            {"document": "test-doc", "query": "SELECT Name, Age FROM People"}
        )
        data = json.loads(result.content[0].text)
        assert "records" in data
        assert len(data["records"]) >= 1
        log = get_mock_request_log()
        assert any("/sql" in entry["path"] for entry in log)

        # ===== WRITE TOOLS =====

        # Test add_records
        clear_mock_request_log()
        new_records = [
            {"Name": "Charlie", "Age": 35, "Email": "charlie@example.com"}
        ]
        result = await client.call_tool(
            "add_records",
            {"document": "test-doc", "table": "People", "records": new_records}
        )
        data = json.loads(result.content[0].text)
        assert "inserted_ids" in data
        assert len(data["inserted_ids"]) == 1
        log = get_mock_request_log()
        post_requests = [e for e in log if e["method"] == "POST" and "/records" in e["path"]]
        assert len(post_requests) >= 1
        assert post_requests[-1]["body"]["records"][0]["fields"]["Name"] == "Charlie"

        # Test update_records
        clear_mock_request_log()
        updates = [{"id": 1, "fields": {"Age": 31}}]
        result = await client.call_tool(
            "update_records",
            {"document": "test-doc", "table": "People", "records": updates}
        )
        data = json.loads(result.content[0].text)
        assert "updated" in data
        log = get_mock_request_log()
        patch_requests = [e for e in log if e["method"] == "PATCH" and "/records" in e["path"]]
        assert len(patch_requests) >= 1

        # Test delete_records
        clear_mock_request_log()
        result = await client.call_tool(
            "delete_records",
            {"document": "test-doc", "table": "People", "record_ids": [1, 2]}
        )
        data = json.loads(result.content[0].text)
        assert "deleted" in data
        log = get_mock_request_log()
        delete_requests = [e for e in log if "/data/delete" in e["path"]]
        assert len(delete_requests) >= 1
        assert delete_requests[-1]["body"] == [1, 2]

        # ===== SCHEMA TOOLS =====

        # Test create_table
        clear_mock_request_log()
        columns = [
            {"id": "Title", "type": "Text"},
            {"id": "Count", "type": "Int"},
        ]
        result = await client.call_tool(
            "create_table",
            {"document": "test-doc", "table_id": "NewTable", "columns": columns}
        )
        data = json.loads(result.content[0].text)
        assert "table_id" in data
        log = get_mock_request_log()
        post_tables = [e for e in log if e["method"] == "POST" and e["path"].endswith("/tables")]
        assert len(post_tables) >= 1

        # Test add_column
        clear_mock_request_log()
        result = await client.call_tool(
            "add_column",
            {
                "document": "test-doc",
                "table": "People",
                "column_id": "Phone",
                "column_type": "Text",
            }
        )
        data = json.loads(result.content[0].text)
        assert "column_id" in data
        log = get_mock_request_log()
        post_cols = [e for e in log if e["method"] == "POST" and "/columns" in e["path"]]
        assert len(post_cols) >= 1

        # Test modify_column
        clear_mock_request_log()
        result = await client.call_tool(
            "modify_column",
            {
                "document": "test-doc",
                "table": "People",
                "column_id": "Age",
                "type": "Numeric",
            }
        )
        data = json.loads(result.content[0].text)
        assert "modified" in data
        log = get_mock_request_log()
        patch_cols = [e for e in log if e["method"] == "PATCH" and "/columns/" in e["path"]]
        assert len(patch_cols) >= 1

        # Test delete_column
        clear_mock_request_log()
        result = await client.call_tool(
            "delete_column",
            {
                "document": "test-doc",
                "table": "People",
                "column_id": "Email",
            }
        )
        data = json.loads(result.content[0].text)
        assert "deleted" in data
        log = get_mock_request_log()
        delete_cols = [e for e in log if e["method"] == "DELETE" and "/columns/" in e["path"]]
        assert len(delete_cols) >= 1

        # ===== AUTHORIZATION =====

        # Test unauthorized document fails
        result = await client.call_tool(
            "list_tables",
            {"document": "unauthorized-doc"}
        )
        assert "error" in result.content[0].text.lower() or "authorization" in result.content[0].text.lower()
