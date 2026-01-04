"""Write tools - create, update, delete records."""

from grist_mcp.auth import Agent, Authenticator, Permission
from grist_mcp.grist_client import GristClient


async def add_records(
    agent: Agent,
    auth: Authenticator,
    document: str,
    table: str,
    records: list[dict],
    client: GristClient | None = None,
) -> dict:
    """Add records to a table."""
    auth.authorize(agent, document, Permission.WRITE)

    if client is None:
        doc = auth.get_document(document)
        client = GristClient(doc)

    ids = await client.add_records(table, records)
    return {"inserted_ids": ids}


async def update_records(
    agent: Agent,
    auth: Authenticator,
    document: str,
    table: str,
    records: list[dict],
    client: GristClient | None = None,
) -> dict:
    """Update existing records."""
    auth.authorize(agent, document, Permission.WRITE)

    if client is None:
        doc = auth.get_document(document)
        client = GristClient(doc)

    await client.update_records(table, records)
    return {"updated": True}


async def delete_records(
    agent: Agent,
    auth: Authenticator,
    document: str,
    table: str,
    record_ids: list[int],
    client: GristClient | None = None,
) -> dict:
    """Delete records by ID."""
    auth.authorize(agent, document, Permission.WRITE)

    if client is None:
        doc = auth.get_document(document)
        client = GristClient(doc)

    await client.delete_records(table, record_ids)
    return {"deleted": True}
