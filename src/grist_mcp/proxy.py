"""HTTP proxy handler for session token access."""

from dataclasses import dataclass
from typing import Any


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
