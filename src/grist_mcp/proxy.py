"""HTTP proxy handler for session token access."""

from dataclasses import dataclass
from typing import Any

from grist_mcp.auth import Authenticator
from grist_mcp.grist_client import GristClient
from grist_mcp.session import SessionToken


class ProxyError(Exception):
    """Error during proxy request processing."""

    def __init__(self, message: str, code: str):
        self.message = message
        self.code = code
        super().__init__(message)


@dataclass
class ProxyRequest:
    """Parsed proxy request."""
    method: str
    table: str | None = None
    records: list[dict] | None = None
    record_ids: list[int] | None = None
    filter: dict | None = None
    sort: str | None = None
    limit: int | None = None
    query: str | None = None
    table_id: str | None = None
    columns: list[dict] | None = None
    column_id: str | None = None
    column_type: str | None = None
    formula: str | None = None
    type: str | None = None


METHODS_REQUIRING_TABLE = {
    "get_records", "describe_table", "add_records", "update_records",
    "delete_records", "add_column", "modify_column", "delete_column",
}


def parse_proxy_request(body: dict[str, Any]) -> ProxyRequest:
    """Parse and validate a proxy request body."""
    if "method" not in body:
        raise ProxyError("Missing required field: method", "INVALID_REQUEST")

    method = body["method"]

    if method in METHODS_REQUIRING_TABLE and "table" not in body:
        raise ProxyError(f"Missing required field 'table' for method '{method}'", "INVALID_REQUEST")

    return ProxyRequest(
        method=method,
        table=body.get("table"),
        records=body.get("records"),
        record_ids=body.get("record_ids"),
        filter=body.get("filter"),
        sort=body.get("sort"),
        limit=body.get("limit"),
        query=body.get("query"),
        table_id=body.get("table_id"),
        columns=body.get("columns"),
        column_id=body.get("column_id"),
        column_type=body.get("column_type"),
        formula=body.get("formula"),
        type=body.get("type"),
    )


# Map methods to required permissions
METHOD_PERMISSIONS = {
    "list_tables": "read",
    "describe_table": "read",
    "get_records": "read",
    "sql_query": "read",
    "add_records": "write",
    "update_records": "write",
    "delete_records": "write",
    "create_table": "schema",
    "add_column": "schema",
    "modify_column": "schema",
    "delete_column": "schema",
}


async def dispatch_proxy_request(
    request: ProxyRequest,
    session: SessionToken,
    auth: Authenticator,
    client: GristClient | None = None,
) -> dict[str, Any]:
    """Dispatch a proxy request to the appropriate handler."""
    # Check permission
    required_perm = METHOD_PERMISSIONS.get(request.method)
    if required_perm is None:
        raise ProxyError(f"Unknown method: {request.method}", "INVALID_REQUEST")

    if required_perm not in session.permissions:
        raise ProxyError(
            f"Permission '{required_perm}' required for {request.method}",
            "UNAUTHORIZED",
        )

    # Create client if not provided
    if client is None:
        doc = auth.get_document(session.document)
        client = GristClient(doc)

    # Dispatch to appropriate method
    try:
        if request.method == "list_tables":
            data = await client.list_tables()
            return {"success": True, "data": {"tables": data}}

        elif request.method == "describe_table":
            data = await client.describe_table(request.table)
            return {"success": True, "data": {"table": request.table, "columns": data}}

        elif request.method == "get_records":
            data = await client.get_records(
                request.table,
                filter=request.filter,
                sort=request.sort,
                limit=request.limit,
            )
            return {"success": True, "data": {"records": data}}

        elif request.method == "sql_query":
            if request.query is None:
                raise ProxyError("Missing required field: query", "INVALID_REQUEST")
            data = await client.sql_query(request.query)
            return {"success": True, "data": {"records": data}}

        elif request.method == "add_records":
            if request.records is None:
                raise ProxyError("Missing required field: records", "INVALID_REQUEST")
            data = await client.add_records(request.table, request.records)
            return {"success": True, "data": {"record_ids": data}}

        elif request.method == "update_records":
            if request.records is None:
                raise ProxyError("Missing required field: records", "INVALID_REQUEST")
            await client.update_records(request.table, request.records)
            return {"success": True, "data": {"updated": len(request.records)}}

        elif request.method == "delete_records":
            if request.record_ids is None:
                raise ProxyError("Missing required field: record_ids", "INVALID_REQUEST")
            await client.delete_records(request.table, request.record_ids)
            return {"success": True, "data": {"deleted": len(request.record_ids)}}

        elif request.method == "create_table":
            if request.table_id is None or request.columns is None:
                raise ProxyError("Missing required fields: table_id, columns", "INVALID_REQUEST")
            data = await client.create_table(request.table_id, request.columns)
            return {"success": True, "data": {"table_id": data}}

        elif request.method == "add_column":
            if request.column_id is None or request.column_type is None:
                raise ProxyError("Missing required fields: column_id, column_type", "INVALID_REQUEST")
            await client.add_column(
                request.table, request.column_id, request.column_type,
                formula=request.formula,
            )
            return {"success": True, "data": {"column_id": request.column_id}}

        elif request.method == "modify_column":
            if request.column_id is None:
                raise ProxyError("Missing required field: column_id", "INVALID_REQUEST")
            await client.modify_column(
                request.table, request.column_id,
                type=request.type,
                formula=request.formula,
            )
            return {"success": True, "data": {"column_id": request.column_id}}

        elif request.method == "delete_column":
            if request.column_id is None:
                raise ProxyError("Missing required field: column_id", "INVALID_REQUEST")
            await client.delete_column(request.table, request.column_id)
            return {"success": True, "data": {"deleted": request.column_id}}

        else:
            raise ProxyError(f"Unknown method: {request.method}", "INVALID_REQUEST")

    except ProxyError:
        raise
    except Exception as e:
        raise ProxyError(str(e), "GRIST_ERROR")
