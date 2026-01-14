import pytest
from unittest.mock import AsyncMock, MagicMock

from grist_mcp.tools.read import list_tables, describe_table, get_records, sql_query
from grist_mcp.auth import Authenticator, Agent, Permission
from grist_mcp.config import Config, Document, Token, TokenScope


@pytest.fixture
def config():
    return Config(
        documents={
            "budget": Document(
                url="https://grist.example.com",
                doc_id="abc123",
                api_key="key",
            ),
        },
        tokens=[
            Token(
                token="test-token",
                name="test-agent",
                scope=[TokenScope(document="budget", permissions=["read"])],
            ),
        ],
    )


@pytest.fixture
def auth(config):
    return Authenticator(config)


@pytest.fixture
def agent(auth):
    return auth.authenticate("test-token")


@pytest.fixture
def mock_client():
    client = AsyncMock()
    client.list_tables.return_value = ["Table1", "Table2"]
    client.describe_table.return_value = [
        {"id": "Name", "type": "Text", "formula": ""},
    ]
    client.get_records.return_value = [
        {"id": 1, "Name": "Alice"},
    ]
    client.sql_query.return_value = [{"Name": "Alice"}]
    return client


@pytest.mark.asyncio
async def test_list_tables(agent, auth, mock_client):
    result = await list_tables(agent, auth, "budget", client=mock_client)

    assert result == {"tables": ["Table1", "Table2"]}
    mock_client.list_tables.assert_called_once()


@pytest.mark.asyncio
async def test_describe_table(agent, auth, mock_client):
    result = await describe_table(agent, auth, "budget", "Table1", client=mock_client)

    assert result == {
        "table": "Table1",
        "columns": [{"id": "Name", "type": "Text", "formula": ""}],
    }


@pytest.mark.asyncio
async def test_get_records(agent, auth, mock_client):
    result = await get_records(agent, auth, "budget", "Table1", client=mock_client)

    assert result == {"records": [{"id": 1, "Name": "Alice"}]}


@pytest.mark.asyncio
async def test_get_records_normalizes_filter(agent, auth, mock_client):
    """Test that filter values are normalized to array format for Grist API."""
    mock_client.get_records.return_value = [{"id": 1, "Customer": 5}]

    await get_records(
        agent, auth, "budget", "Orders",
        filter={"Customer": 5, "Status": "active"},
        client=mock_client,
    )

    # Verify filter was normalized: single values wrapped in lists
    mock_client.get_records.assert_called_once_with(
        "Orders",
        filter={"Customer": [5], "Status": ["active"]},
        sort=None,
        limit=None,
    )


@pytest.mark.asyncio
async def test_get_records_preserves_list_filter(agent, auth, mock_client):
    """Test that filter values already in list format are preserved."""
    mock_client.get_records.return_value = []

    await get_records(
        agent, auth, "budget", "Orders",
        filter={"Customer": [5, 6, 7]},
        client=mock_client,
    )

    mock_client.get_records.assert_called_once_with(
        "Orders",
        filter={"Customer": [5, 6, 7]},
        sort=None,
        limit=None,
    )


@pytest.mark.asyncio
async def test_sql_query(agent, auth, mock_client):
    result = await sql_query(agent, auth, "budget", "SELECT * FROM Table1", client=mock_client)

    assert result == {"records": [{"Name": "Alice"}]}
