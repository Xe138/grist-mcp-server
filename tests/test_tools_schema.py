import pytest
from unittest.mock import AsyncMock

from grist_mcp.tools.schema import create_table, add_column, modify_column, delete_column
from grist_mcp.auth import Authenticator, AuthError
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
                token="schema-token",
                name="schema-agent",
                scope=[TokenScope(document="budget", permissions=["read", "write", "schema"])],
            ),
            Token(
                token="write-token",
                name="write-agent",
                scope=[TokenScope(document="budget", permissions=["read", "write"])],
            ),
        ],
    )


@pytest.fixture
def auth(config):
    return Authenticator(config)


@pytest.fixture
def mock_client():
    client = AsyncMock()
    client.create_table.return_value = "NewTable"
    client.add_column.return_value = "NewCol"
    client.modify_column.return_value = None
    client.delete_column.return_value = None
    return client


@pytest.mark.asyncio
async def test_create_table(auth, mock_client):
    agent = auth.authenticate("schema-token")

    result = await create_table(
        agent, auth, "budget", "NewTable",
        columns=[{"id": "Name", "type": "Text"}],
        client=mock_client,
    )

    assert result == {"table_id": "NewTable"}


@pytest.mark.asyncio
async def test_create_table_denied_without_schema(auth, mock_client):
    agent = auth.authenticate("write-token")

    with pytest.raises(AuthError, match="Permission denied"):
        await create_table(
            agent, auth, "budget", "NewTable",
            columns=[{"id": "Name", "type": "Text"}],
            client=mock_client,
        )


@pytest.mark.asyncio
async def test_add_column(auth, mock_client):
    agent = auth.authenticate("schema-token")

    result = await add_column(
        agent, auth, "budget", "Table1", "NewCol", "Text",
        client=mock_client,
    )

    assert result == {"column_id": "NewCol"}


@pytest.mark.asyncio
async def test_modify_column(auth, mock_client):
    agent = auth.authenticate("schema-token")

    result = await modify_column(
        agent, auth, "budget", "Table1", "Col1",
        type="Int",
        formula="$A + $B",
        client=mock_client,
    )

    assert result == {"modified": True}


@pytest.mark.asyncio
async def test_delete_column(auth, mock_client):
    agent = auth.authenticate("schema-token")

    result = await delete_column(
        agent, auth, "budget", "Table1", "OldCol",
        client=mock_client,
    )

    assert result == {"deleted": True}
