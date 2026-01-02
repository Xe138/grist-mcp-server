import pytest
from datetime import datetime, timedelta, timezone

from grist_mcp.session import SessionTokenManager, SessionToken


def test_create_token_returns_valid_session_token():
    manager = SessionTokenManager()

    token = manager.create_token(
        agent_name="test-agent",
        document="sales",
        permissions=["read", "write"],
        ttl_seconds=300,
    )

    assert token.token.startswith("sess_")
    assert len(token.token) > 20
    assert token.document == "sales"
    assert token.permissions == ["read", "write"]
    assert token.agent_name == "test-agent"
    assert token.expires_at > datetime.now(timezone.utc)
    assert token.expires_at < datetime.now(timezone.utc) + timedelta(seconds=310)


def test_create_token_caps_ttl_at_maximum():
    manager = SessionTokenManager()

    # Request 2 hours, should be capped at 1 hour
    token = manager.create_token(
        agent_name="test-agent",
        document="sales",
        permissions=["read"],
        ttl_seconds=7200,
    )

    # Should be capped at 3600 seconds (1 hour)
    max_expires = datetime.now(timezone.utc) + timedelta(seconds=3610)
    assert token.expires_at < max_expires
