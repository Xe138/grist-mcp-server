"""Session token tools for HTTP proxy access."""

from grist_mcp.auth import Agent, Authenticator, AuthError, Permission
from grist_mcp.session import SessionTokenManager


PROXY_DOCUMENTATION = {
    "description": "HTTP proxy API for bulk data operations. Use request_session_token to get a short-lived token, then call the proxy endpoint directly from scripts.",
    "endpoint": "POST /api/v1/proxy",
    "authentication": "Bearer token in Authorization header",
    "request_format": {
        "method": "Operation name (required)",
        "table": "Table name (required for most operations)",
    },
    "methods": {
        "get_records": {
            "description": "Fetch records from a table",
            "fields": {
                "table": "string",
                "filter": "object (optional)",
                "sort": "string (optional)",
                "limit": "integer (optional)",
            },
        },
        "sql_query": {
            "description": "Run a read-only SQL query",
            "fields": {"query": "string"},
        },
        "list_tables": {
            "description": "List all tables in the document",
            "fields": {},
        },
        "describe_table": {
            "description": "Get column information for a table",
            "fields": {"table": "string"},
        },
        "add_records": {
            "description": "Add records to a table",
            "fields": {"table": "string", "records": "array of objects"},
        },
        "update_records": {
            "description": "Update existing records",
            "fields": {"table": "string", "records": "array of {id, fields}"},
        },
        "delete_records": {
            "description": "Delete records by ID",
            "fields": {"table": "string", "record_ids": "array of integers"},
        },
        "create_table": {
            "description": "Create a new table",
            "fields": {"table_id": "string", "columns": "array of {id, type}"},
        },
        "add_column": {
            "description": "Add a column to a table",
            "fields": {
                "table": "string",
                "column_id": "string",
                "column_type": "string",
                "formula": "string (optional)",
            },
        },
        "modify_column": {
            "description": "Modify a column's type or formula",
            "fields": {
                "table": "string",
                "column_id": "string",
                "type": "string (optional)",
                "formula": "string (optional)",
            },
        },
        "delete_column": {
            "description": "Delete a column",
            "fields": {"table": "string", "column_id": "string"},
        },
    },
    "response_format": {
        "success": {"success": True, "data": "..."},
        "error": {"success": False, "error": "message", "code": "ERROR_CODE"},
    },
    "error_codes": [
        "UNAUTHORIZED",
        "INVALID_TOKEN",
        "TOKEN_EXPIRED",
        "INVALID_REQUEST",
        "GRIST_ERROR",
    ],
    "example_script": """#!/usr/bin/env python3
import requests
import sys

token = sys.argv[1]
host = sys.argv[2]

response = requests.post(
    f'{host}/api/v1/proxy',
    headers={'Authorization': f'Bearer {token}'},
    json={
        'method': 'add_records',
        'table': 'Orders',
        'records': [{'item': 'Widget', 'qty': 100}]
    }
)
print(response.json())
""",
}


async def get_proxy_documentation() -> dict:
    """Return complete documentation for the HTTP proxy API."""
    return PROXY_DOCUMENTATION


async def request_session_token(
    agent: Agent,
    auth: Authenticator,
    token_manager: SessionTokenManager,
    document: str,
    permissions: list[str],
    ttl_seconds: int = 300,
) -> dict:
    """Request a short-lived session token for HTTP proxy access.

    The token can only grant permissions the agent already has.
    """
    # Verify agent has access to the document
    # Check each requested permission
    for perm_str in permissions:
        try:
            perm = Permission(perm_str)
        except ValueError:
            raise AuthError(f"Invalid permission: {perm_str}")
        auth.authorize(agent, document, perm)

    # Create the session token
    session = token_manager.create_token(
        agent_name=agent.name,
        document=document,
        permissions=permissions,
        ttl_seconds=ttl_seconds,
    )

    return {
        "token": session.token,
        "document": session.document,
        "permissions": session.permissions,
        "expires_at": session.expires_at.isoformat(),
        "proxy_url": "/api/v1/proxy",
    }
