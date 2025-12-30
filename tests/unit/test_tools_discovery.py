import pytest
from grist_mcp.tools.discovery import list_documents
from grist_mcp.auth import Agent
from grist_mcp.config import Token, TokenScope


@pytest.fixture
def agent():
    token_obj = Token(
        token="test-token",
        name="test-agent",
        scope=[
            TokenScope(document="budget", permissions=["read", "write"]),
            TokenScope(document="expenses", permissions=["read"]),
        ],
    )
    return Agent(token="test-token", name="test-agent", _token_obj=token_obj)


@pytest.mark.asyncio
async def test_list_documents_returns_accessible_docs(agent):
    result = await list_documents(agent)

    assert result == {
        "documents": [
            {"name": "budget", "permissions": ["read", "write"]},
            {"name": "expenses", "permissions": ["read"]},
        ]
    }
