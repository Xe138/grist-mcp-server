import pytest
from grist_mcp.tools.session import get_proxy_documentation, request_session_token
from grist_mcp.auth import Authenticator, Agent, AuthError
from grist_mcp.config import Config, Document, Token, TokenScope
from grist_mcp.session import SessionTokenManager


@pytest.fixture
def sample_config():
    return Config(
        documents={
            "sales": Document(
                url="https://grist.example.com",
                doc_id="abc123",
                api_key="key",
            ),
        },
        tokens=[
            Token(
                token="agent-token",
                name="test-agent",
                scope=[
                    TokenScope(document="sales", permissions=["read", "write"]),
                ],
            ),
        ],
    )


@pytest.fixture
def auth_and_agent(sample_config):
    auth = Authenticator(sample_config)
    agent = auth.authenticate("agent-token")
    return auth, agent


@pytest.mark.asyncio
async def test_get_proxy_documentation_returns_complete_spec():
    result = await get_proxy_documentation()

    assert "description" in result
    assert "endpoints" in result
    assert "proxy" in result["endpoints"]
    assert "attachments_upload" in result["endpoints"]
    assert "attachments_download" in result["endpoints"]
    assert "authentication" in result
    assert "methods" in result
    assert "add_records" in result["methods"]
    assert "get_records" in result["methods"]
    assert "attachment_upload" in result
    assert "attachment_download" in result
    assert "example_script" in result


@pytest.mark.asyncio
async def test_request_session_token_creates_valid_token(auth_and_agent):
    auth, agent = auth_and_agent
    manager = SessionTokenManager()

    result = await request_session_token(
        agent=agent,
        auth=auth,
        token_manager=manager,
        document="sales",
        permissions=["read", "write"],
        ttl_seconds=300,
    )

    assert "token" in result
    assert result["token"].startswith("sess_")
    assert result["document"] == "sales"
    assert result["permissions"] == ["read", "write"]
    assert "expires_at" in result
    assert result["proxy_url"] == "/api/v1/proxy"


@pytest.mark.asyncio
async def test_request_session_token_rejects_unauthorized_document(sample_config):
    auth = Authenticator(sample_config)
    agent = auth.authenticate("agent-token")
    manager = SessionTokenManager()

    with pytest.raises(AuthError, match="Document not in scope"):
        await request_session_token(
            agent=agent,
            auth=auth,
            token_manager=manager,
            document="unauthorized_doc",
            permissions=["read"],
            ttl_seconds=300,
        )


@pytest.mark.asyncio
async def test_request_session_token_rejects_unauthorized_permission(sample_config):
    auth = Authenticator(sample_config)
    agent = auth.authenticate("agent-token")
    manager = SessionTokenManager()

    # Agent has read/write on sales, but not schema
    with pytest.raises(AuthError, match="Permission denied"):
        await request_session_token(
            agent=agent,
            auth=auth,
            token_manager=manager,
            document="sales",
            permissions=["read", "schema"],  # schema not granted
            ttl_seconds=300,
        )


@pytest.mark.asyncio
async def test_request_session_token_rejects_invalid_permission(sample_config):
    auth = Authenticator(sample_config)
    agent = auth.authenticate("agent-token")
    manager = SessionTokenManager()

    with pytest.raises(AuthError, match="Invalid permission"):
        await request_session_token(
            agent=agent,
            auth=auth,
            token_manager=manager,
            document="sales",
            permissions=["read", "invalid_perm"],
            ttl_seconds=300,
        )
