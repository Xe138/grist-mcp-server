import base64

import pytest
from unittest.mock import AsyncMock

from grist_mcp.tools.write import add_records, update_records, delete_records, upload_attachment
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


# Upload attachment tests

@pytest.fixture
def mock_client_with_attachment():
    client = AsyncMock()
    client.upload_attachment.return_value = {
        "attachment_id": 42,
        "filename": "invoice.pdf",
        "size_bytes": 1024,
    }
    return client


@pytest.mark.asyncio
async def test_upload_attachment_success(auth, mock_client_with_attachment):
    agent = auth.authenticate("write-token")
    content = b"PDF content"
    content_base64 = base64.b64encode(content).decode()

    result = await upload_attachment(
        agent, auth, "budget",
        filename="invoice.pdf",
        content_base64=content_base64,
        client=mock_client_with_attachment,
    )

    assert result == {
        "attachment_id": 42,
        "filename": "invoice.pdf",
        "size_bytes": 1024,
    }
    mock_client_with_attachment.upload_attachment.assert_called_once_with(
        "invoice.pdf", content, "application/pdf"
    )


@pytest.mark.asyncio
async def test_upload_attachment_invalid_base64(auth, mock_client_with_attachment):
    agent = auth.authenticate("write-token")

    with pytest.raises(ValueError, match="Invalid base64 encoding"):
        await upload_attachment(
            agent, auth, "budget",
            filename="test.txt",
            content_base64="not-valid-base64!!!",
            client=mock_client_with_attachment,
        )


@pytest.mark.asyncio
async def test_upload_attachment_auth_required(auth, mock_client_with_attachment):
    agent = auth.authenticate("read-token")
    content_base64 = base64.b64encode(b"test").decode()

    with pytest.raises(AuthError, match="Permission denied"):
        await upload_attachment(
            agent, auth, "budget",
            filename="test.txt",
            content_base64=content_base64,
            client=mock_client_with_attachment,
        )


@pytest.mark.asyncio
async def test_upload_attachment_mime_detection(auth, mock_client_with_attachment):
    agent = auth.authenticate("write-token")
    content = b"PNG content"
    content_base64 = base64.b64encode(content).decode()

    await upload_attachment(
        agent, auth, "budget",
        filename="image.png",
        content_base64=content_base64,
        client=mock_client_with_attachment,
    )

    # Should auto-detect image/png from filename
    mock_client_with_attachment.upload_attachment.assert_called_once_with(
        "image.png", content, "image/png"
    )


@pytest.mark.asyncio
async def test_upload_attachment_explicit_content_type(auth, mock_client_with_attachment):
    agent = auth.authenticate("write-token")
    content = b"custom content"
    content_base64 = base64.b64encode(content).decode()

    await upload_attachment(
        agent, auth, "budget",
        filename="file.dat",
        content_base64=content_base64,
        content_type="application/custom",
        client=mock_client_with_attachment,
    )

    # Should use explicit content type
    mock_client_with_attachment.upload_attachment.assert_called_once_with(
        "file.dat", content, "application/custom"
    )
