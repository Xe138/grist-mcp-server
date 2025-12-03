"""Schema tools - create and modify tables and columns."""

from grist_mcp.auth import Agent, Authenticator, Permission
from grist_mcp.grist_client import GristClient


async def create_table(
    agent: Agent,
    auth: Authenticator,
    document: str,
    table_id: str,
    columns: list[dict],
    client: GristClient | None = None,
) -> dict:
    """Create a new table with columns."""
    auth.authorize(agent, document, Permission.SCHEMA)

    if client is None:
        doc = auth.get_document(document)
        client = GristClient(doc)

    created_id = await client.create_table(table_id, columns)
    return {"table_id": created_id}


async def add_column(
    agent: Agent,
    auth: Authenticator,
    document: str,
    table: str,
    column_id: str,
    column_type: str,
    formula: str | None = None,
    client: GristClient | None = None,
) -> dict:
    """Add a column to a table."""
    auth.authorize(agent, document, Permission.SCHEMA)

    if client is None:
        doc = auth.get_document(document)
        client = GristClient(doc)

    created_id = await client.add_column(table, column_id, column_type, formula=formula)
    return {"column_id": created_id}


async def modify_column(
    agent: Agent,
    auth: Authenticator,
    document: str,
    table: str,
    column_id: str,
    type: str | None = None,
    formula: str | None = None,
    client: GristClient | None = None,
) -> dict:
    """Modify a column's type or formula."""
    auth.authorize(agent, document, Permission.SCHEMA)

    if client is None:
        doc = auth.get_document(document)
        client = GristClient(doc)

    await client.modify_column(table, column_id, type=type, formula=formula)
    return {"modified": True}


async def delete_column(
    agent: Agent,
    auth: Authenticator,
    document: str,
    table: str,
    column_id: str,
    client: GristClient | None = None,
) -> dict:
    """Delete a column from a table."""
    auth.authorize(agent, document, Permission.SCHEMA)

    if client is None:
        doc = auth.get_document(document)
        client = GristClient(doc)

    await client.delete_column(table, column_id)
    return {"deleted": True}
