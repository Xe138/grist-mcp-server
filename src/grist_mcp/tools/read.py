"""Read tools - query tables and records."""

from grist_mcp.auth import Agent, Authenticator, Permission
from grist_mcp.grist_client import GristClient
from grist_mcp.tools.filters import normalize_filter


async def list_tables(
    agent: Agent,
    auth: Authenticator,
    document: str,
    client: GristClient | None = None,
) -> dict:
    """List all tables in a document."""
    auth.authorize(agent, document, Permission.READ)

    if client is None:
        doc = auth.get_document(document)
        client = GristClient(doc)

    tables = await client.list_tables()
    return {"tables": tables}


async def describe_table(
    agent: Agent,
    auth: Authenticator,
    document: str,
    table: str,
    client: GristClient | None = None,
) -> dict:
    """Get column information for a table."""
    auth.authorize(agent, document, Permission.READ)

    if client is None:
        doc = auth.get_document(document)
        client = GristClient(doc)

    columns = await client.describe_table(table)
    return {"table": table, "columns": columns}


async def get_records(
    agent: Agent,
    auth: Authenticator,
    document: str,
    table: str,
    filter: dict | None = None,
    sort: str | None = None,
    limit: int | None = None,
    client: GristClient | None = None,
) -> dict:
    """Fetch records from a table."""
    auth.authorize(agent, document, Permission.READ)

    if client is None:
        doc = auth.get_document(document)
        client = GristClient(doc)

    # Normalize filter values to array format for Grist API
    normalized_filter = normalize_filter(filter)

    records = await client.get_records(table, filter=normalized_filter, sort=sort, limit=limit)
    return {"records": records}


async def sql_query(
    agent: Agent,
    auth: Authenticator,
    document: str,
    query: str,
    client: GristClient | None = None,
) -> dict:
    """Run a read-only SQL query."""
    auth.authorize(agent, document, Permission.READ)

    if client is None:
        doc = auth.get_document(document)
        client = GristClient(doc)

    records = await client.sql_query(query)
    return {"records": records}
