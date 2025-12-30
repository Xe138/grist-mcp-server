"""Test tool calls through MCP client to verify Grist API interactions."""

import json

import pytest


@pytest.mark.asyncio
async def test_list_documents(mcp_client):
    """Test list_documents returns accessible documents."""
    result = await mcp_client.call_tool("list_documents", {})

    assert len(result.content) == 1
    data = json.loads(result.content[0].text)

    assert "documents" in data
    assert len(data["documents"]) == 1
    assert data["documents"][0]["name"] == "test-doc"
    assert "read" in data["documents"][0]["permissions"]


@pytest.mark.asyncio
async def test_list_tables(mcp_client, mock_grist_client):
    """Test list_tables calls correct Grist API endpoint."""
    result = await mcp_client.call_tool("list_tables", {"document": "test-doc"})

    # Check response
    data = json.loads(result.content[0].text)
    assert "tables" in data
    assert "People" in data["tables"]
    assert "Tasks" in data["tables"]

    # Verify mock received correct request
    log = mock_grist_client.get("/_test/requests").json()
    assert len(log) >= 1
    assert log[-1]["method"] == "GET"
    assert "/tables" in log[-1]["path"]


@pytest.mark.asyncio
async def test_describe_table(mcp_client, mock_grist_client):
    """Test describe_table returns column information."""
    result = await mcp_client.call_tool(
        "describe_table",
        {"document": "test-doc", "table": "People"}
    )

    data = json.loads(result.content[0].text)
    assert "columns" in data

    column_ids = [c["id"] for c in data["columns"]]
    assert "Name" in column_ids
    assert "Age" in column_ids

    # Verify API call
    log = mock_grist_client.get("/_test/requests").json()
    assert any("/columns" in entry["path"] for entry in log)


@pytest.mark.asyncio
async def test_get_records(mcp_client, mock_grist_client):
    """Test get_records fetches records from table."""
    result = await mcp_client.call_tool(
        "get_records",
        {"document": "test-doc", "table": "People"}
    )

    data = json.loads(result.content[0].text)
    assert "records" in data
    assert len(data["records"]) == 2
    assert data["records"][0]["Name"] == "Alice"

    # Verify API call
    log = mock_grist_client.get("/_test/requests").json()
    assert any("/records" in entry["path"] and entry["method"] == "GET" for entry in log)


@pytest.mark.asyncio
async def test_sql_query(mcp_client, mock_grist_client):
    """Test sql_query executes SQL and returns results."""
    result = await mcp_client.call_tool(
        "sql_query",
        {"document": "test-doc", "query": "SELECT Name, Age FROM People"}
    )

    data = json.loads(result.content[0].text)
    assert "records" in data
    assert len(data["records"]) >= 1

    # Verify API call
    log = mock_grist_client.get("/_test/requests").json()
    assert any("/sql" in entry["path"] for entry in log)


@pytest.mark.asyncio
async def test_add_records(mcp_client, mock_grist_client):
    """Test add_records sends correct payload to Grist."""
    new_records = [
        {"Name": "Charlie", "Age": 35, "Email": "charlie@example.com"}
    ]

    result = await mcp_client.call_tool(
        "add_records",
        {"document": "test-doc", "table": "People", "records": new_records}
    )

    data = json.loads(result.content[0].text)
    assert "record_ids" in data
    assert len(data["record_ids"]) == 1

    # Verify API call body
    log = mock_grist_client.get("/_test/requests").json()
    post_requests = [e for e in log if e["method"] == "POST" and "/records" in e["path"]]
    assert len(post_requests) >= 1
    assert post_requests[-1]["body"]["records"][0]["fields"]["Name"] == "Charlie"


@pytest.mark.asyncio
async def test_update_records(mcp_client, mock_grist_client):
    """Test update_records sends correct payload to Grist."""
    updates = [
        {"id": 1, "fields": {"Age": 31}}
    ]

    result = await mcp_client.call_tool(
        "update_records",
        {"document": "test-doc", "table": "People", "records": updates}
    )

    data = json.loads(result.content[0].text)
    assert "updated" in data

    # Verify API call
    log = mock_grist_client.get("/_test/requests").json()
    patch_requests = [e for e in log if e["method"] == "PATCH" and "/records" in e["path"]]
    assert len(patch_requests) >= 1


@pytest.mark.asyncio
async def test_delete_records(mcp_client, mock_grist_client):
    """Test delete_records sends correct IDs to Grist."""
    result = await mcp_client.call_tool(
        "delete_records",
        {"document": "test-doc", "table": "People", "record_ids": [1, 2]}
    )

    data = json.loads(result.content[0].text)
    assert "deleted" in data

    # Verify API call
    log = mock_grist_client.get("/_test/requests").json()
    delete_requests = [e for e in log if "/data/delete" in e["path"]]
    assert len(delete_requests) >= 1
    assert delete_requests[-1]["body"] == [1, 2]


@pytest.mark.asyncio
async def test_create_table(mcp_client, mock_grist_client):
    """Test create_table sends correct schema to Grist."""
    columns = [
        {"id": "Title", "type": "Text"},
        {"id": "Count", "type": "Int"},
    ]

    result = await mcp_client.call_tool(
        "create_table",
        {"document": "test-doc", "table_id": "NewTable", "columns": columns}
    )

    data = json.loads(result.content[0].text)
    assert "table_id" in data

    # Verify API call
    log = mock_grist_client.get("/_test/requests").json()
    post_tables = [e for e in log if e["method"] == "POST" and e["path"].endswith("/tables")]
    assert len(post_tables) >= 1


@pytest.mark.asyncio
async def test_add_column(mcp_client, mock_grist_client):
    """Test add_column sends correct column definition."""
    result = await mcp_client.call_tool(
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

    # Verify API call
    log = mock_grist_client.get("/_test/requests").json()
    post_cols = [e for e in log if e["method"] == "POST" and "/columns" in e["path"]]
    assert len(post_cols) >= 1


@pytest.mark.asyncio
async def test_modify_column(mcp_client, mock_grist_client):
    """Test modify_column sends correct update."""
    result = await mcp_client.call_tool(
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

    # Verify API call
    log = mock_grist_client.get("/_test/requests").json()
    patch_cols = [e for e in log if e["method"] == "PATCH" and "/columns/" in e["path"]]
    assert len(patch_cols) >= 1


@pytest.mark.asyncio
async def test_delete_column(mcp_client, mock_grist_client):
    """Test delete_column calls correct endpoint."""
    result = await mcp_client.call_tool(
        "delete_column",
        {
            "document": "test-doc",
            "table": "People",
            "column_id": "Email",
        }
    )

    data = json.loads(result.content[0].text)
    assert "deleted" in data

    # Verify API call
    log = mock_grist_client.get("/_test/requests").json()
    delete_cols = [e for e in log if e["method"] == "DELETE" and "/columns/" in e["path"]]
    assert len(delete_cols) >= 1


@pytest.mark.asyncio
async def test_unauthorized_document_fails(mcp_client):
    """Test that accessing unauthorized document returns error."""
    result = await mcp_client.call_tool(
        "list_tables",
        {"document": "unauthorized-doc"}
    )

    assert "error" in result.content[0].text.lower() or "authorization" in result.content[0].text.lower()
