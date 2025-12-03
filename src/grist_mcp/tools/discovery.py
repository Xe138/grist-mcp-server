"""Discovery tools - list accessible documents."""

from grist_mcp.auth import Agent


async def list_documents(agent: Agent) -> dict:
    """List documents this agent can access with their permissions."""
    documents = [
        {"name": scope.document, "permissions": scope.permissions}
        for scope in agent._token_obj.scope
    ]
    return {"documents": documents}
