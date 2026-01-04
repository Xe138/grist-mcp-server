import pytest
from unittest.mock import AsyncMock

from grist_mcp.tools.write import add_records, update_records, delete_records
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
                token="write-token",
                name="write-agent",
                scope=[TokenScope(document="budget", permissions=["read", "write"])],
            ),
            Token(
                token="read-token",
                name="read-agent",
                scope=[TokenScope(document="budget", permissions=["read"])],
            ),
        ],
    )


@pytest.fixture
def auth(config):
    return Authenticator(config)


@pytest.fixture
def mock_client():
    client = AsyncMock()
    client.add_records.return_value = [1, 2]
    client.update_records.return_value = None
    client.delete_records.return_value = None
    return client


@pytest.mark.asyncio
async def test_add_records(auth, mock_client):
    agent = auth.authenticate("write-token")

    result = await add_records(
        agent, auth, "budget", "Table1",
        records=[{"Name": "Alice"}, {"Name": "Bob"}],
        client=mock_client,
    )

    assert result == {"inserted_ids": [1, 2]}


@pytest.mark.asyncio
async def test_add_records_denied_without_write(auth, mock_client):
    agent = auth.authenticate("read-token")

    with pytest.raises(AuthError, match="Permission denied"):
        await add_records(
            agent, auth, "budget", "Table1",
            records=[{"Name": "Alice"}],
            client=mock_client,
        )


@pytest.mark.asyncio
async def test_update_records(auth, mock_client):
    agent = auth.authenticate("write-token")

    result = await update_records(
        agent, auth, "budget", "Table1",
        records=[{"id": 1, "fields": {"Name": "Updated"}}],
        client=mock_client,
    )

    assert result == {"updated": True}


@pytest.mark.asyncio
async def test_delete_records(auth, mock_client):
    agent = auth.authenticate("write-token")

    result = await delete_records(
        agent, auth, "budget", "Table1",
        record_ids=[1, 2],
        client=mock_client,
    )

    assert result == {"deleted": True}
