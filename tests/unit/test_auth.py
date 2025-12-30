import pytest
from grist_mcp.auth import Authenticator, AuthError, Permission
from grist_mcp.config import Config, Document, Token, TokenScope


@pytest.fixture
def sample_config():
    return Config(
        documents={
            "budget": Document(
                url="https://grist.example.com",
                doc_id="abc123",
                api_key="doc-api-key",
            ),
            "expenses": Document(
                url="https://grist.example.com",
                doc_id="def456",
                api_key="doc-api-key",
            ),
        },
        tokens=[
            Token(
                token="valid-token",
                name="test-agent",
                scope=[
                    TokenScope(document="budget", permissions=["read", "write"]),
                    TokenScope(document="expenses", permissions=["read"]),
                ],
            ),
        ],
    )


def test_authenticate_valid_token(sample_config):
    auth = Authenticator(sample_config)
    agent = auth.authenticate("valid-token")

    assert agent.name == "test-agent"
    assert agent.token == "valid-token"


def test_authenticate_invalid_token(sample_config):
    auth = Authenticator(sample_config)

    with pytest.raises(AuthError, match="Invalid token"):
        auth.authenticate("bad-token")


def test_authorize_allowed_document_and_permission(sample_config):
    auth = Authenticator(sample_config)
    agent = auth.authenticate("valid-token")

    # Should not raise
    auth.authorize(agent, "budget", Permission.READ)
    auth.authorize(agent, "budget", Permission.WRITE)
    auth.authorize(agent, "expenses", Permission.READ)


def test_authorize_denied_document(sample_config):
    auth = Authenticator(sample_config)
    agent = auth.authenticate("valid-token")

    with pytest.raises(AuthError, match="Document not in scope"):
        auth.authorize(agent, "unknown-doc", Permission.READ)


def test_authorize_denied_permission(sample_config):
    auth = Authenticator(sample_config)
    agent = auth.authenticate("valid-token")

    # expenses only has read permission
    with pytest.raises(AuthError, match="Permission denied"):
        auth.authorize(agent, "expenses", Permission.WRITE)


def test_get_accessible_documents(sample_config):
    auth = Authenticator(sample_config)
    agent = auth.authenticate("valid-token")

    docs = auth.get_accessible_documents(agent)

    assert len(docs) == 2
    assert {"name": "budget", "permissions": ["read", "write"]} in docs
    assert {"name": "expenses", "permissions": ["read"]} in docs


def test_get_document_returns_document(sample_config):
    auth = Authenticator(sample_config)

    doc = auth.get_document("budget")

    assert doc.doc_id == "abc123"


def test_get_document_raises_on_unknown(sample_config):
    auth = Authenticator(sample_config)

    with pytest.raises(AuthError, match="Document 'unknown' not configured"):
        auth.get_document("unknown")
