"""Integration tests for session token proxy."""

import os
import pytest
import httpx


GRIST_MCP_URL = os.environ.get("GRIST_MCP_URL", "http://localhost:3000")
GRIST_MCP_TOKEN = os.environ.get("GRIST_MCP_TOKEN")


@pytest.fixture
def mcp_client():
    """Client for MCP SSE endpoint."""
    return httpx.Client(
        base_url=GRIST_MCP_URL,
        headers={"Authorization": f"Bearer {GRIST_MCP_TOKEN}"},
    )


@pytest.fixture
def proxy_client():
    """Client for proxy endpoint (session token set per-test)."""
    return httpx.Client(base_url=GRIST_MCP_URL)


@pytest.mark.integration
def test_full_session_proxy_flow(mcp_client, proxy_client):
    """Test: request token via MCP, use token to call proxy."""
    # This test requires a running grist-mcp server with proper config
    # Skip if not configured
    if not GRIST_MCP_TOKEN:
        pytest.skip("GRIST_MCP_TOKEN not set")

    # Step 1: Request session token (would be via MCP in real usage)
    # For integration test, we test the proxy endpoint directly
    # This is a placeholder - full MCP integration would use SSE

    # Step 2: Use proxy endpoint
    # Note: Need a valid session token to test this fully
    # For now, verify endpoint exists and rejects bad tokens

    response = proxy_client.post(
        "/api/v1/proxy",
        headers={"Authorization": "Bearer invalid_token"},
        json={"method": "list_tables"},
    )

    assert response.status_code == 401
    data = response.json()
    assert data["success"] is False
    assert data["code"] in ["INVALID_TOKEN", "TOKEN_EXPIRED"]
