# Session Token Proxy Design

## Problem

When an agent needs to insert, update, or query thousands of records, the LLM must generate all that JSON in its response. This is slow regardless of how fast the actual API call is. The LLM generation time is the bottleneck.

## Solution

Add a "session token" mechanism that lets agents delegate bulk data operations to scripts that call grist-mcp directly over HTTP, bypassing LLM generation entirely.

## Flow

```
1. Agent calls MCP tool:
   request_session_token(document="sales", permissions=["write"], ttl_seconds=300)

2. Server generates token, stores in memory:
   {"sess_abc123...": {document: "sales", permissions: ["write"], expires: <timestamp>}}

3. Server returns token to agent:
   {"token": "sess_abc123...", "expires_in": 300, "proxy_url": "/api/v1/proxy"}

4. Agent spawns script with token:
   python bulk_insert.py --token sess_abc123... --file data.csv

5. Script calls grist-mcp HTTP endpoint:
   POST /api/v1/proxy
   Authorization: Bearer sess_abc123...
   {"table": "Orders", "method": "add_records", "records": [...]}

6. Server validates token, executes against Grist, returns result
```

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Token scope | Single document + permission level | Simpler than multi-doc; matches existing permission model |
| Token storage | In-memory dict | Appropriate for short-lived tokens; restart invalidates (acceptable) |
| HTTP interface | Wrapped endpoint `/api/v1/proxy` | Simpler than mirroring Grist API paths |
| Request format | Discrete fields (table, method, etc.) | Scripts don't need to know Grist internals or doc IDs |
| Document in request | Implicit from token | Token is scoped to one document; no need to specify |
| Server architecture | Single process, add routes | Already running HTTP for SSE; just add routes |

## MCP Tool: request_session_token

**Input schema**:
```json
{
  "type": "object",
  "properties": {
    "document": {
      "type": "string",
      "description": "Document name to grant access to"
    },
    "permissions": {
      "type": "array",
      "items": {"type": "string", "enum": ["read", "write", "schema"]},
      "description": "Permission levels to grant (cannot exceed agent's permissions)"
    },
    "ttl_seconds": {
      "type": "integer",
      "description": "Token lifetime in seconds (max 3600, default 300)"
    }
  },
  "required": ["document", "permissions"]
}
```

**Response**:
```json
{
  "token": "sess_a1b2c3d4...",
  "document": "sales",
  "permissions": ["write"],
  "expires_at": "2025-01-02T15:30:00Z",
  "proxy_url": "/api/v1/proxy"
}
```

**Validation**:
- Agent must have access to the requested document
- Requested permissions cannot exceed agent's permissions for that document
- TTL capped at 3600 seconds (1 hour), default 300 seconds (5 minutes)

## Proxy Endpoint

**Endpoint**: `POST /api/v1/proxy`

**Authentication**: `Authorization: Bearer <session_token>`

**Request body** - method determines required fields:

```python
# Read operations
{"method": "get_records", "table": "Orders", "filter": {...}, "sort": "date", "limit": 1000}
{"method": "sql_query", "query": "SELECT * FROM Orders WHERE amount > 100"}
{"method": "list_tables"}
{"method": "describe_table", "table": "Orders"}

# Write operations
{"method": "add_records", "table": "Orders", "records": [{...}, {...}]}
{"method": "update_records", "table": "Orders", "records": [{"id": 1, "fields": {...}}]}
{"method": "delete_records", "table": "Orders", "record_ids": [1, 2, 3]}

# Schema operations
{"method": "create_table", "table_id": "NewTable", "columns": [{...}]}
{"method": "add_column", "table": "Orders", "column_id": "status", "column_type": "Text"}
{"method": "modify_column", "table": "Orders", "column_id": "status", "type": "Choice"}
{"method": "delete_column", "table": "Orders", "column_id": "old_field"}
```

**Response format**:
```json
{"success": true, "data": {...}}
{"success": false, "error": "Permission denied", "code": "UNAUTHORIZED"}
```

**Error codes**:
- `UNAUTHORIZED` - Permission denied for this operation
- `INVALID_TOKEN` - Token format invalid or not found
- `TOKEN_EXPIRED` - Token has expired
- `INVALID_REQUEST` - Malformed request body
- `GRIST_ERROR` - Error from Grist API

## Implementation Architecture

### New Files

**`src/grist_mcp/session.py`** - Session token management:
```python
@dataclass
class SessionToken:
    token: str
    document: str
    permissions: list[str]
    agent_name: str
    created_at: datetime
    expires_at: datetime

class SessionTokenManager:
    def __init__(self):
        self._tokens: dict[str, SessionToken] = {}

    def create_token(self, agent: Agent, document: str,
                     permissions: list[str], ttl_seconds: int) -> SessionToken:
        """Create a new session token. Validates permissions against agent's scope."""
        ...

    def validate_token(self, token: str) -> SessionToken | None:
        """Validate token and return session info. Returns None if invalid/expired."""
        # Also cleans up this token if expired
        ...

    def cleanup_expired(self) -> int:
        """Remove all expired tokens. Returns count removed."""
        ...
```

**`src/grist_mcp/proxy.py`** - HTTP proxy handler:
```python
async def handle_proxy(
    scope: Scope,
    receive: Receive,
    send: Send,
    token_manager: SessionTokenManager,
    auth: Authenticator
) -> None:
    """Handle POST /api/v1/proxy requests."""
    # 1. Extract Bearer token from Authorization header
    # 2. Validate session token
    # 3. Parse request body (method, table, etc.)
    # 4. Check permissions for requested method
    # 5. Build GristClient for the token's document
    # 6. Dispatch to appropriate tool function
    # 7. Return JSON response
```

### Modified Files

**`src/grist_mcp/main.py`**:
- Import `SessionTokenManager` and `handle_proxy`
- Instantiate `SessionTokenManager` in `create_app()`
- Add route: `elif path == "/api/v1/proxy" and method == "POST"`
- Pass `token_manager` to `create_server()`

**`src/grist_mcp/server.py`**:
- Accept `token_manager` parameter in `create_server()`
- Add `request_session_token` tool to `list_tools()`
- Add handler in `call_tool()` that creates token via `token_manager.create_token()`

## Security

1. **No privilege escalation** - Session token can only grant permissions the agent already has for the document. Validated at token creation.

2. **Short-lived by default** - 5 minute default TTL, 1 hour maximum cap.

3. **Token format** - Prefixed with `sess_` to distinguish from agent tokens. Generated with `secrets.token_urlsafe(32)`.

4. **Lazy cleanup** - Expired tokens removed during validation. No background task needed.

5. **Audit logging** - Token creation and proxy requests logged with agent name, document, method.

## Testing

### Unit Tests

**`tests/unit/test_session.py`**:
- Token creation with valid permissions
- Token creation fails when exceeding agent permissions
- Token validation succeeds for valid token
- Token validation fails for expired token
- Token validation fails for unknown token
- TTL capping at maximum
- Cleanup removes expired tokens

**`tests/unit/test_proxy.py`**:
- Request parsing for each method type
- Error response for invalid token
- Error response for expired token
- Error response for permission denied
- Error response for malformed request
- Successful dispatch to each tool function (mocked)

### Integration Tests

**`tests/integration/test_session_proxy.py`**:
- Full flow: MCP token request → HTTP proxy call → Grist operation
- Verify data actually written to Grist
- Verify token expiry prevents access
