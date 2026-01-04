import pytest
from pytest_httpx import HTTPXMock

from grist_mcp.grist_client import GristClient
from grist_mcp.config import Document


@pytest.fixture
def doc():
    return Document(
        url="https://grist.example.com",
        doc_id="abc123",
        api_key="test-api-key",
    )


@pytest.fixture
def client(doc):
    return GristClient(doc)


@pytest.mark.asyncio
async def test_list_tables(client, httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        url="https://grist.example.com/api/docs/abc123/tables",
        json={"tables": [{"id": "Table1"}, {"id": "Table2"}]},
    )

    tables = await client.list_tables()

    assert tables == ["Table1", "Table2"]


@pytest.mark.asyncio
async def test_describe_table(client, httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        url="https://grist.example.com/api/docs/abc123/tables/Table1/columns",
        json={
            "columns": [
                {"id": "Name", "fields": {"type": "Text", "formula": ""}},
                {"id": "Amount", "fields": {"type": "Numeric", "formula": "$Price * $Qty"}},
            ]
        },
    )

    columns = await client.describe_table("Table1")

    assert len(columns) == 2
    assert columns[0] == {"id": "Name", "type": "Text", "formula": ""}
    assert columns[1] == {"id": "Amount", "type": "Numeric", "formula": "$Price * $Qty"}


@pytest.mark.asyncio
async def test_get_records(client, httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        url="https://grist.example.com/api/docs/abc123/tables/Table1/records",
        json={
            "records": [
                {"id": 1, "fields": {"Name": "Alice", "Amount": 100}},
                {"id": 2, "fields": {"Name": "Bob", "Amount": 200}},
            ]
        },
    )

    records = await client.get_records("Table1")

    assert len(records) == 2
    assert records[0] == {"id": 1, "Name": "Alice", "Amount": 100}


@pytest.mark.asyncio
async def test_add_records(client, httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        url="https://grist.example.com/api/docs/abc123/tables/Table1/records",
        method="POST",
        json={"records": [{"id": 3}, {"id": 4}]},
    )

    ids = await client.add_records("Table1", [
        {"Name": "Charlie", "Amount": 300},
        {"Name": "Diana", "Amount": 400},
    ])

    assert ids == [3, 4]


@pytest.mark.asyncio
async def test_update_records(client, httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        url="https://grist.example.com/api/docs/abc123/tables/Table1/records",
        method="PATCH",
        json={},
    )

    # Should not raise
    await client.update_records("Table1", [
        {"id": 1, "fields": {"Amount": 150}},
    ])


@pytest.mark.asyncio
async def test_delete_records(client, httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        url="https://grist.example.com/api/docs/abc123/tables/Table1/data/delete",
        method="POST",
        json={},
    )

    # Should not raise
    await client.delete_records("Table1", [1, 2])


@pytest.mark.asyncio
async def test_sql_query(client, httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        url="https://grist.example.com/api/docs/abc123/sql?q=SELECT+*+FROM+Table1",
        method="GET",
        json={
            "statement": "SELECT * FROM Table1",
            "records": [
                {"fields": {"Name": "Alice", "Amount": 100}},
            ],
        },
    )

    result = await client.sql_query("SELECT * FROM Table1")

    assert result == [{"Name": "Alice", "Amount": 100}]


@pytest.mark.asyncio
async def test_create_table(client, httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        url="https://grist.example.com/api/docs/abc123/tables",
        method="POST",
        json={"tables": [{"id": "NewTable"}]},
    )

    table_id = await client.create_table("NewTable", [
        {"id": "Col1", "type": "Text"},
        {"id": "Col2", "type": "Numeric"},
    ])

    assert table_id == "NewTable"


@pytest.mark.asyncio
async def test_add_column(client, httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        url="https://grist.example.com/api/docs/abc123/tables/Table1/columns",
        method="POST",
        json={"columns": [{"id": "NewCol"}]},
    )

    col_id = await client.add_column("Table1", "NewCol", "Text", formula=None)

    assert col_id == "NewCol"


@pytest.mark.asyncio
async def test_modify_column(client, httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        url="https://grist.example.com/api/docs/abc123/tables/Table1/columns",
        method="PATCH",
        json={},
    )

    # Should not raise
    await client.modify_column("Table1", "Amount", type="Int", formula="$Price * $Qty")


@pytest.mark.asyncio
async def test_delete_column(client, httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        url="https://grist.example.com/api/docs/abc123/tables/Table1/columns/OldCol",
        method="DELETE",
        json={},
    )

    # Should not raise
    await client.delete_column("Table1", "OldCol")


# SQL validation tests

def test_sql_validation_rejects_non_select(client):
    with pytest.raises(ValueError, match="Only SELECT queries are allowed"):
        client._validate_sql_query("DROP TABLE users")


def test_sql_validation_rejects_multiple_statements(client):
    with pytest.raises(ValueError, match="Multiple statements not allowed"):
        client._validate_sql_query("SELECT * FROM users; DROP TABLE users")


def test_sql_validation_allows_trailing_semicolon(client):
    # Should not raise
    client._validate_sql_query("SELECT * FROM users;")


# Attachment tests

@pytest.mark.asyncio
async def test_upload_attachment(client, httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        url="https://grist.example.com/api/docs/abc123/attachments",
        method="POST",
        json=[42],
    )

    result = await client.upload_attachment(
        filename="invoice.pdf",
        content=b"PDF content here",
        content_type="application/pdf",
    )

    assert result == {
        "attachment_id": 42,
        "filename": "invoice.pdf",
        "size_bytes": 16,
    }


@pytest.mark.asyncio
async def test_upload_attachment_default_content_type(client, httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        url="https://grist.example.com/api/docs/abc123/attachments",
        method="POST",
        json=[99],
    )

    result = await client.upload_attachment(
        filename="data.bin",
        content=b"\x00\x01\x02",
    )

    assert result["attachment_id"] == 99
    assert result["size_bytes"] == 3
