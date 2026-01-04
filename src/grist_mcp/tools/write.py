"""Write tools - create, update, delete records, upload attachments."""

import base64
import mimetypes

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


async def upload_attachment(
    agent: Agent,
    auth: Authenticator,
    document: str,
    filename: str,
    content_base64: str,
    content_type: str | None = None,
    client: GristClient | None = None,
) -> dict:
    """Upload a file attachment to a document.

    Args:
        agent: The authenticated agent.
        auth: Authenticator for permission checks.
        document: Document name.
        filename: Filename with extension.
        content_base64: File content as base64-encoded string.
        content_type: MIME type (auto-detected from filename if omitted).
        client: Optional GristClient instance.

    Returns:
        Dict with attachment_id, filename, and size_bytes.

    Raises:
        ValueError: If content_base64 is not valid base64.
    """
    auth.authorize(agent, document, Permission.WRITE)

    # Decode base64 content
    try:
        content = base64.b64decode(content_base64)
    except Exception:
        raise ValueError("Invalid base64 encoding")

    # Auto-detect MIME type if not provided
    if content_type is None:
        content_type, _ = mimetypes.guess_type(filename)
        if content_type is None:
            content_type = "application/octet-stream"

    if client is None:
        doc = auth.get_document(document)
        client = GristClient(doc)

    return await client.upload_attachment(filename, content, content_type)
