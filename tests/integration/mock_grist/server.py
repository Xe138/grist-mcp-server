"""Mock Grist API server for integration testing."""

import json
import logging
import os
from datetime import datetime, timezone

from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route

logging.basicConfig(level=logging.INFO, format="%(asctime)s [MOCK-GRIST] %(message)s")
logger = logging.getLogger(__name__)

# Mock data
MOCK_TABLES = {
    "People": {
        "columns": [
            {"id": "Name", "fields": {"type": "Text"}},
            {"id": "Age", "fields": {"type": "Int"}},
            {"id": "Email", "fields": {"type": "Text"}},
        ],
        "records": [
            {"id": 1, "fields": {"Name": "Alice", "Age": 30, "Email": "alice@example.com"}},
            {"id": 2, "fields": {"Name": "Bob", "Age": 25, "Email": "bob@example.com"}},
        ],
    },
    "Tasks": {
        "columns": [
            {"id": "Title", "fields": {"type": "Text"}},
            {"id": "Done", "fields": {"type": "Bool"}},
        ],
        "records": [
            {"id": 1, "fields": {"Title": "Write tests", "Done": False}},
            {"id": 2, "fields": {"Title": "Deploy", "Done": False}},
        ],
    },
    "Orders": {
        "columns": [
            {"id": "OrderNum", "fields": {"type": "Int"}},
            {"id": "Customer", "fields": {"type": "Ref:People"}},
            {"id": "Amount", "fields": {"type": "Numeric"}},
        ],
        "records": [
            {"id": 1, "fields": {"OrderNum": 1001, "Customer": 1, "Amount": 100.0}},
            {"id": 2, "fields": {"OrderNum": 1002, "Customer": 2, "Amount": 200.0}},
            {"id": 3, "fields": {"OrderNum": 1003, "Customer": 1, "Amount": 150.0}},
        ],
    },
}

# Track requests for test assertions
request_log: list[dict] = []


def log_request(method: str, path: str, body: dict | None = None):
    """Log a request for later inspection."""
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "method": method,
        "path": path,
        "body": body,
    }
    request_log.append(entry)
    logger.info(f"{method} {path}" + (f" body={json.dumps(body)}" if body else ""))


async def health(request):
    """Health check endpoint."""
    return JSONResponse({"status": "ok"})


async def get_request_log(request):
    """Return the request log for test assertions."""
    return JSONResponse(request_log)


async def clear_request_log(request):
    """Clear the request log."""
    request_log.clear()
    return JSONResponse({"status": "cleared"})


async def list_tables(request):
    """GET /api/docs/{doc_id}/tables"""
    doc_id = request.path_params["doc_id"]
    log_request("GET", f"/api/docs/{doc_id}/tables")
    tables = [{"id": name} for name in MOCK_TABLES.keys()]
    return JSONResponse({"tables": tables})


async def get_table_columns(request):
    """GET /api/docs/{doc_id}/tables/{table_id}/columns"""
    doc_id = request.path_params["doc_id"]
    table_id = request.path_params["table_id"]
    log_request("GET", f"/api/docs/{doc_id}/tables/{table_id}/columns")

    if table_id not in MOCK_TABLES:
        return JSONResponse({"error": "Table not found"}, status_code=404)

    return JSONResponse({"columns": MOCK_TABLES[table_id]["columns"]})


async def get_records(request):
    """GET /api/docs/{doc_id}/tables/{table_id}/records"""
    doc_id = request.path_params["doc_id"]
    table_id = request.path_params["table_id"]
    filter_param = request.query_params.get("filter")
    log_request("GET", f"/api/docs/{doc_id}/tables/{table_id}/records?filter={filter_param}")

    if table_id not in MOCK_TABLES:
        return JSONResponse({"error": "Table not found"}, status_code=404)

    records = MOCK_TABLES[table_id]["records"]

    # Apply filtering if provided
    if filter_param:
        try:
            filters = json.loads(filter_param)
            # Validate filter format: all values must be arrays (Grist API requirement)
            for key, values in filters.items():
                if not isinstance(values, list):
                    return JSONResponse(
                        {"error": f"Filter values must be arrays, got {type(values).__name__} for '{key}'"},
                        status_code=400
                    )
            # Apply filters: record matches if field value is in the filter list
            filtered_records = []
            for record in records:
                match = True
                for key, allowed_values in filters.items():
                    if record["fields"].get(key) not in allowed_values:
                        match = False
                        break
                if match:
                    filtered_records.append(record)
            records = filtered_records
        except json.JSONDecodeError:
            return JSONResponse({"error": "Invalid filter JSON"}, status_code=400)

    return JSONResponse({"records": records})


async def add_records(request):
    """POST /api/docs/{doc_id}/tables/{table_id}/records"""
    doc_id = request.path_params["doc_id"]
    table_id = request.path_params["table_id"]
    body = await request.json()
    log_request("POST", f"/api/docs/{doc_id}/tables/{table_id}/records", body)

    # Return mock IDs for new records
    new_ids = [{"id": 100 + i} for i in range(len(body.get("records", [])))]
    return JSONResponse({"records": new_ids})


async def update_records(request):
    """PATCH /api/docs/{doc_id}/tables/{table_id}/records"""
    doc_id = request.path_params["doc_id"]
    table_id = request.path_params["table_id"]
    body = await request.json()
    log_request("PATCH", f"/api/docs/{doc_id}/tables/{table_id}/records", body)
    return JSONResponse({})


async def delete_records(request):
    """POST /api/docs/{doc_id}/tables/{table_id}/data/delete"""
    doc_id = request.path_params["doc_id"]
    table_id = request.path_params["table_id"]
    body = await request.json()
    log_request("POST", f"/api/docs/{doc_id}/tables/{table_id}/data/delete", body)
    return JSONResponse({})


async def sql_query(request):
    """GET /api/docs/{doc_id}/sql"""
    doc_id = request.path_params["doc_id"]
    query = request.query_params.get("q", "")
    log_request("GET", f"/api/docs/{doc_id}/sql?q={query}")

    # Return mock SQL results
    return JSONResponse({
        "records": [
            {"fields": {"Name": "Alice", "Age": 30}},
            {"fields": {"Name": "Bob", "Age": 25}},
        ]
    })


async def create_tables(request):
    """POST /api/docs/{doc_id}/tables"""
    doc_id = request.path_params["doc_id"]
    body = await request.json()
    log_request("POST", f"/api/docs/{doc_id}/tables", body)

    # Return the created tables with their IDs
    tables = [{"id": t["id"]} for t in body.get("tables", [])]
    return JSONResponse({"tables": tables})


async def add_column(request):
    """POST /api/docs/{doc_id}/tables/{table_id}/columns"""
    doc_id = request.path_params["doc_id"]
    table_id = request.path_params["table_id"]
    body = await request.json()
    log_request("POST", f"/api/docs/{doc_id}/tables/{table_id}/columns", body)

    columns = [{"id": c["id"]} for c in body.get("columns", [])]
    return JSONResponse({"columns": columns})


async def modify_column(request):
    """PATCH /api/docs/{doc_id}/tables/{table_id}/columns/{col_id}"""
    doc_id = request.path_params["doc_id"]
    table_id = request.path_params["table_id"]
    col_id = request.path_params["col_id"]
    body = await request.json()
    log_request("PATCH", f"/api/docs/{doc_id}/tables/{table_id}/columns/{col_id}", body)
    return JSONResponse({})


async def modify_columns(request):
    """PATCH /api/docs/{doc_id}/tables/{table_id}/columns - batch modify columns"""
    doc_id = request.path_params["doc_id"]
    table_id = request.path_params["table_id"]
    body = await request.json()
    log_request("PATCH", f"/api/docs/{doc_id}/tables/{table_id}/columns", body)
    return JSONResponse({})


async def delete_column(request):
    """DELETE /api/docs/{doc_id}/tables/{table_id}/columns/{col_id}"""
    doc_id = request.path_params["doc_id"]
    table_id = request.path_params["table_id"]
    col_id = request.path_params["col_id"]
    log_request("DELETE", f"/api/docs/{doc_id}/tables/{table_id}/columns/{col_id}")
    return JSONResponse({})


app = Starlette(
    routes=[
        # Test control endpoints
        Route("/health", endpoint=health),
        Route("/_test/requests", endpoint=get_request_log),
        Route("/_test/requests/clear", endpoint=clear_request_log, methods=["POST"]),

        # Grist API endpoints
        Route("/api/docs/{doc_id}/tables", endpoint=list_tables),
        Route("/api/docs/{doc_id}/tables", endpoint=create_tables, methods=["POST"]),
        Route("/api/docs/{doc_id}/tables/{table_id}/columns", endpoint=get_table_columns),
        Route("/api/docs/{doc_id}/tables/{table_id}/columns", endpoint=add_column, methods=["POST"]),
        Route("/api/docs/{doc_id}/tables/{table_id}/columns", endpoint=modify_columns, methods=["PATCH"]),
        Route("/api/docs/{doc_id}/tables/{table_id}/columns/{col_id}", endpoint=modify_column, methods=["PATCH"]),
        Route("/api/docs/{doc_id}/tables/{table_id}/columns/{col_id}", endpoint=delete_column, methods=["DELETE"]),
        Route("/api/docs/{doc_id}/tables/{table_id}/records", endpoint=get_records),
        Route("/api/docs/{doc_id}/tables/{table_id}/records", endpoint=add_records, methods=["POST"]),
        Route("/api/docs/{doc_id}/tables/{table_id}/records", endpoint=update_records, methods=["PATCH"]),
        Route("/api/docs/{doc_id}/tables/{table_id}/data/delete", endpoint=delete_records, methods=["POST"]),
        Route("/api/docs/{doc_id}/sql", endpoint=sql_query),
    ]
)


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", "8484"))
    logger.info(f"Starting mock Grist server on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)
