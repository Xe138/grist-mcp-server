# Attachment Upload Feature Design

**Date:** 2026-01-03
**Status:** Approved

## Summary

Add an `upload_attachment` MCP tool to upload files to Grist documents and receive an attachment ID for linking to records.

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Content encoding | Base64 string | MCP tools use JSON; binary must be encoded |
| Batch support | Single file only | YAGNI; caller can loop if needed |
| Linking behavior | Upload only, return ID | Single responsibility; use existing `update_records` to link |
| Download support | Not included | YAGNI; can add later if needed |
| Permission level | Write | Attachments are data, not schema |
| Proxy support | MCP tool only | Reduces scope; scripts can use Grist API directly |

## Tool Interface

### Input Schema

```json
{
  "type": "object",
  "properties": {
    "document": {
      "type": "string",
      "description": "Document name"
    },
    "filename": {
      "type": "string",
      "description": "Filename with extension (e.g., 'invoice.pdf')"
    },
    "content_base64": {
      "type": "string",
      "description": "File content as base64-encoded string"
    },
    "content_type": {
      "type": "string",
      "description": "MIME type (optional, auto-detected from filename if omitted)"
    }
  },
  "required": ["document", "filename", "content_base64"]
}
```

### Response

```json
{
  "attachment_id": 42,
  "filename": "invoice.pdf",
  "size_bytes": 30720
}
```

### Usage Example

```python
# 1. Upload attachment
result = upload_attachment(
    document="accounting",
    filename="Invoice-001.pdf",
    content_base64="JVBERi0xLjQK..."
)

# 2. Link to record via existing update_records tool
update_records("Bills", [{
    "id": 1,
    "fields": {"Attachment": [result["attachment_id"]]}
}])
```

## Implementation

### Files to Modify

1. **`src/grist_mcp/grist_client.py`** - Add `upload_attachment()` method
2. **`src/grist_mcp/tools/write.py`** - Add tool function
3. **`src/grist_mcp/server.py`** - Register tool

### GristClient Method

```python
async def upload_attachment(
    self,
    filename: str,
    content: bytes,
    content_type: str | None = None
) -> dict:
    """Upload a file attachment. Returns attachment metadata."""
    if content_type is None:
        content_type = "application/octet-stream"

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
```

### Tool Function

```python
import base64
import mimetypes

async def upload_attachment(
    agent: Agent,
    auth: Authenticator,
    document: str,
    filename: str,
    content_base64: str,
    content_type: str | None = None,
    client: GristClient | None = None,
) -> dict:
    """Upload a file attachment to a document."""
    auth.authorize(agent, document, Permission.WRITE)

    # Decode base64
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
```

## Error Handling

| Error | Cause | Response |
|-------|-------|----------|
| Invalid base64 | Malformed content_base64 | `ValueError: Invalid base64 encoding` |
| Authorization | Agent lacks write permission | `AuthError` (existing pattern) |
| Grist API error | Upload fails | `httpx.HTTPStatusError` (existing pattern) |

## Testing

### Unit Tests

**`tests/unit/test_tools_write.py`:**
- `test_upload_attachment_success` - Valid base64, returns attachment_id
- `test_upload_attachment_invalid_base64` - Raises ValueError
- `test_upload_attachment_auth_required` - Verifies write permission check
- `test_upload_attachment_mime_detection` - Auto-detects type from filename

**`tests/unit/test_grist_client.py`:**
- `test_upload_attachment_api_call` - Correct multipart request format
- `test_upload_attachment_with_explicit_content_type` - Passes through MIME type

### Mock Approach

Mock `httpx.AsyncClient` responses; no Grist server needed for unit tests.

## Future Considerations

Not included in this implementation (YAGNI):
- Batch upload (multiple files)
- Download attachment
- Proxy API support
- Size limit validation (rely on Grist's limits)

These can be added if real use cases emerge.
