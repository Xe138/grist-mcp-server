from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from grist_mcp.proxy import parse_proxy_request, ProxyRequest, ProxyError, dispatch_proxy_request
from grist_mcp.session import SessionToken


@pytest.fixture
def mock_session():
    return SessionToken(
        token="sess_test",
        document="sales",
        permissions=["read", "write"],
        agent_name="test-agent",
        created_at=datetime.now(timezone.utc),
        expires_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def mock_auth():
    auth = MagicMock()
    doc = MagicMock()
    doc.url = "https://grist.example.com"
    doc.doc_id = "abc123"
    doc.api_key = "key"
    auth.get_document.return_value = doc
    return auth


def test_parse_proxy_request_valid_add_records():
    body = {
        "method": "add_records",
        "table": "Orders",
        "records": [{"item": "Widget", "qty": 10}],
    }

    request = parse_proxy_request(body)

    assert request.method == "add_records"
    assert request.table == "Orders"
    assert request.records == [{"item": "Widget", "qty": 10}]


def test_parse_proxy_request_missing_method():
    body = {"table": "Orders"}

    with pytest.raises(ProxyError) as exc_info:
        parse_proxy_request(body)

    assert exc_info.value.code == "INVALID_REQUEST"
    assert "method" in str(exc_info.value)


@pytest.mark.asyncio
async def test_dispatch_add_records(mock_session, mock_auth):
    request = ProxyRequest(
        method="add_records",
        table="Orders",
        records=[{"item": "Widget"}],
    )

    mock_client = AsyncMock()
    mock_client.add_records.return_value = [1, 2, 3]

    result = await dispatch_proxy_request(
        request, mock_session, mock_auth, client=mock_client
    )

    assert result["success"] is True
    assert result["data"]["record_ids"] == [1, 2, 3]
    mock_client.add_records.assert_called_once_with("Orders", [{"item": "Widget"}])


@pytest.mark.asyncio
async def test_dispatch_denies_without_permission(mock_auth):
    # Session only has read permission
    session = SessionToken(
        token="sess_test",
        document="sales",
        permissions=["read"],  # No write
        agent_name="test-agent",
        created_at=datetime.now(timezone.utc),
        expires_at=datetime.now(timezone.utc),
    )

    request = ProxyRequest(
        method="add_records",  # Requires write
        table="Orders",
        records=[{"item": "Widget"}],
    )

    with pytest.raises(ProxyError) as exc_info:
        await dispatch_proxy_request(request, session, mock_auth)

    assert exc_info.value.code == "UNAUTHORIZED"
