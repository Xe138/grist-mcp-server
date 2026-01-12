"""Grist API client."""

import json

import httpx

from grist_mcp.config import Document

# Default timeout for HTTP requests (30 seconds)
DEFAULT_TIMEOUT = 30.0


class GristClient:
    """Async client for Grist API operations."""

    def __init__(self, document: Document, timeout: float = DEFAULT_TIMEOUT):
        self._doc = document
        self._base_url = f"{document.url.rstrip('/')}/api/docs/{document.doc_id}"
        self._headers = {"Authorization": f"Bearer {document.api_key}"}
        if document.host_header:
            self._headers["Host"] = document.host_header
        self._timeout = timeout

    async def _request(self, method: str, path: str, **kwargs) -> dict:
        """Make an authenticated request to Grist API."""
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.request(
                method,
                f"{self._base_url}{path}",
                headers=self._headers,
                **kwargs,
            )
            response.raise_for_status()
            return response.json() if response.content else {}

    # Read operations

    async def list_tables(self) -> list[str]:
        """List all tables in the document."""
        data = await self._request("GET", "/tables")
        return [t["id"] for t in data.get("tables", [])]

    async def describe_table(self, table: str) -> list[dict]:
        """Get column information for a table."""
        data = await self._request("GET", f"/tables/{table}/columns")
        return [
            {
                "id": col["id"],
                "type": col["fields"].get("type", "Any"),
                "formula": col["fields"].get("formula", ""),
            }
            for col in data.get("columns", [])
        ]

    async def get_records(
        self,
        table: str,
        filter: dict | None = None,
        sort: str | None = None,
        limit: int | None = None,
    ) -> list[dict]:
        """Fetch records from a table."""
        params = {}
        if filter:
            params["filter"] = json.dumps(filter)
        if sort:
            params["sort"] = sort
        if limit:
            params["limit"] = limit

        data = await self._request("GET", f"/tables/{table}/records", params=params)

        return [
            {"id": r["id"], **r["fields"]}
            for r in data.get("records", [])
        ]

    async def sql_query(self, sql: str) -> list[dict]:
        """Run a read-only SQL query.

        Raises:
            ValueError: If query is not a SELECT statement or contains multiple statements.
        """
        self._validate_sql_query(sql)
        data = await self._request("GET", "/sql", params={"q": sql})
        return [r["fields"] for r in data.get("records", [])]

    @staticmethod
    def _validate_sql_query(sql: str) -> None:
        """Validate SQL query for safety.

        Only allows SELECT statements and rejects multiple statements.
        """
        sql_stripped = sql.strip()
        if not sql_stripped.upper().startswith("SELECT"):
            raise ValueError("Only SELECT queries are allowed")
        if ";" in sql_stripped[:-1]:  # Allow trailing semicolon
            raise ValueError("Multiple statements not allowed")

    # Write operations

    async def add_records(self, table: str, records: list[dict]) -> list[int]:
        """Add records to a table. Returns list of new record IDs."""
        payload = {
            "records": [{"fields": r} for r in records]
        }
        data = await self._request("POST", f"/tables/{table}/records", json=payload)
        return [r["id"] for r in data.get("records", [])]

    async def update_records(self, table: str, records: list[dict]) -> None:
        """Update records. Each record must have 'id' and 'fields' keys."""
        payload = {"records": records}
        await self._request("PATCH", f"/tables/{table}/records", json=payload)

    async def delete_records(self, table: str, record_ids: list[int]) -> None:
        """Delete records by ID."""
        await self._request("POST", f"/tables/{table}/data/delete", json=record_ids)

    async def upload_attachment(
        self,
        filename: str,
        content: bytes,
        content_type: str = "application/octet-stream",
    ) -> dict:
        """Upload a file attachment. Returns attachment metadata.

        Args:
            filename: Name for the uploaded file.
            content: File content as bytes.
            content_type: MIME type of the file.

        Returns:
            Dict with attachment_id, filename, and size_bytes.
        """
        files = {"upload": (filename, content, content_type)}

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(
                f"{self._base_url}/attachments",
                headers=self._headers,
                files=files,
            )
            response.raise_for_status()
            # Grist returns list of attachment IDs
            attachment_ids = response.json()
            return {
                "attachment_id": attachment_ids[0],
                "filename": filename,
                "size_bytes": len(content),
            }

    async def download_attachment(self, attachment_id: int) -> dict:
        """Download an attachment by ID.

        Args:
            attachment_id: The ID of the attachment to download.

        Returns:
            Dict with content (bytes), content_type, and filename.
        """
        import re

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.get(
                f"{self._base_url}/attachments/{attachment_id}/download",
                headers=self._headers,
            )
            response.raise_for_status()

            # Extract filename from Content-Disposition header
            content_disp = response.headers.get("content-disposition", "")
            filename = None
            if "filename=" in content_disp:
                match = re.search(r'filename="?([^";]+)"?', content_disp)
                if match:
                    filename = match.group(1)

            return {
                "content": response.content,
                "content_type": response.headers.get("content-type", "application/octet-stream"),
                "filename": filename,
            }

    # Schema operations

    async def create_table(self, table_id: str, columns: list[dict]) -> str:
        """Create a new table with columns. Returns table ID."""
        payload = {
            "tables": [{
                "id": table_id,
                "columns": [
                    {"id": c["id"], "fields": {"type": c["type"]}}
                    for c in columns
                ],
            }]
        }
        data = await self._request("POST", "/tables", json=payload)
        return data["tables"][0]["id"]

    async def add_column(
        self,
        table: str,
        column_id: str,
        column_type: str,
        formula: str | None = None,
    ) -> str:
        """Add a column to a table. Returns column ID."""
        fields = {"type": column_type}
        if formula:
            fields["formula"] = formula

        payload = {"columns": [{"id": column_id, "fields": fields}]}
        data = await self._request("POST", f"/tables/{table}/columns", json=payload)
        return data["columns"][0]["id"]

    async def modify_column(
        self,
        table: str,
        column_id: str,
        type: str | None = None,
        formula: str | None = None,
    ) -> None:
        """Modify a column's type or formula."""
        fields = {}
        if type is not None:
            fields["type"] = type
        if formula is not None:
            fields["formula"] = formula

        payload = {"columns": [{"id": column_id, "fields": fields}]}
        await self._request("PATCH", f"/tables/{table}/columns", json=payload)

    async def delete_column(self, table: str, column_id: str) -> None:
        """Delete a column from a table."""
        await self._request("DELETE", f"/tables/{table}/columns/{column_id}")
