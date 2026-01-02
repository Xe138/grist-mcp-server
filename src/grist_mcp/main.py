"""Main entry point for the MCP server with SSE transport."""

import json
import logging
import os
import sys
from typing import Any

import uvicorn
from mcp.server.sse import SseServerTransport

from grist_mcp.server import create_server
from grist_mcp.config import Config, load_config
from grist_mcp.auth import Authenticator, AuthError
from grist_mcp.session import SessionTokenManager
from grist_mcp.proxy import parse_proxy_request, dispatch_proxy_request, ProxyError
from grist_mcp.logging import setup_logging


Scope = dict[str, Any]
Receive = Any
Send = Any


def _get_bearer_token(scope: Scope) -> str | None:
    """Extract Bearer token from Authorization header."""
    headers = dict(scope.get("headers", []))
    auth_header = headers.get(b"authorization", b"").decode()
    if auth_header.startswith("Bearer "):
        return auth_header[7:]
    return None


async def send_error(send: Send, status: int, message: str) -> None:
    """Send an HTTP error response."""
    body = json.dumps({"error": message}).encode()
    await send({
        "type": "http.response.start",
        "status": status,
        "headers": [[b"content-type", b"application/json"]],
    })
    await send({
        "type": "http.response.body",
        "body": body,
    })


async def send_json_response(send: Send, status: int, data: dict) -> None:
    """Send a JSON response."""
    body = json.dumps(data).encode()
    await send({
        "type": "http.response.start",
        "status": status,
        "headers": [[b"content-type", b"application/json"]],
    })
    await send({
        "type": "http.response.body",
        "body": body,
    })


CONFIG_TEMPLATE = """\
# grist-mcp configuration
#
# Token Generation:
#   python -c "import secrets; print(secrets.token_urlsafe(32))"
#   openssl rand -base64 32

# Document definitions
documents:
  my-document:
    url: https://docs.getgrist.com
    doc_id: YOUR_DOC_ID
    api_key: ${GRIST_API_KEY}

# Agent tokens with access scopes
tokens:
  - token: REPLACE_WITH_GENERATED_TOKEN
    name: my-agent
    scope:
      - document: my-document
        permissions: [read, write]
"""


def _ensure_config(config_path: str) -> bool:
    """Ensure config file exists. Creates template if missing.

    Returns True if config is ready, False if template was created.
    """
    path = os.path.abspath(config_path)

    # Check if path is a directory (Docker creates this when mounting missing file)
    if os.path.isdir(path):
        print(f"ERROR: Config path is a directory: {path}")
        print()
        print("This usually means the config file doesn't exist on the host.")
        print("Please create the config file before starting the container:")
        print()
        print(f"  mkdir -p $(dirname {config_path})")
        print(f"  cat > {config_path} << 'EOF'")
        print(CONFIG_TEMPLATE)
        print("EOF")
        print()
        return False

    if os.path.exists(path):
        return True

    # Create template config
    try:
        with open(path, "w") as f:
            f.write(CONFIG_TEMPLATE)
        print(f"Created template configuration at: {path}")
        print()
        print("Please edit this file to configure your Grist documents and agent tokens,")
        print("then restart the server.")
    except PermissionError:
        print(f"ERROR: Cannot create config file at: {path}")
        print()
        print("Please create the config file manually before starting the container.")
        print()
    return False


def create_app(config: Config):
    """Create the ASGI application."""
    auth = Authenticator(config)
    token_manager = SessionTokenManager()
    proxy_base_url = os.environ.get("GRIST_MCP_URL")

    sse = SseServerTransport("/messages")

    async def handle_sse(scope: Scope, receive: Receive, send: Send) -> None:
        # Extract and validate token from Authorization header
        token = _get_bearer_token(scope)
        if not token:
            await send_error(send, 401, "Missing Authorization header")
            return

        try:
            agent = auth.authenticate(token)
        except AuthError as e:
            await send_error(send, 401, str(e))
            return

        # Create a server instance for this authenticated connection
        server = create_server(auth, agent, token_manager, proxy_base_url)

        async with sse.connect_sse(scope, receive, send) as streams:
            await server.run(
                streams[0], streams[1], server.create_initialization_options()
            )

    async def handle_messages(scope: Scope, receive: Receive, send: Send) -> None:
        await sse.handle_post_message(scope, receive, send)

    async def handle_health(scope: Scope, receive: Receive, send: Send) -> None:
        await send({
            "type": "http.response.start",
            "status": 200,
            "headers": [[b"content-type", b"application/json"]],
        })
        await send({
            "type": "http.response.body",
            "body": b'{"status":"ok"}',
        })

    async def handle_not_found(scope: Scope, receive: Receive, send: Send) -> None:
        await send({
            "type": "http.response.start",
            "status": 404,
            "headers": [[b"content-type", b"application/json"]],
        })
        await send({
            "type": "http.response.body",
            "body": b'{"error":"Not found"}',
        })

    async def handle_proxy(scope: Scope, receive: Receive, send: Send) -> None:
        # Extract token
        token = _get_bearer_token(scope)
        if not token:
            await send_json_response(send, 401, {
                "success": False,
                "error": "Missing Authorization header",
                "code": "INVALID_TOKEN",
            })
            return

        # Validate session token
        session = token_manager.validate_token(token)
        if session is None:
            await send_json_response(send, 401, {
                "success": False,
                "error": "Invalid or expired token",
                "code": "TOKEN_EXPIRED",
            })
            return

        # Read request body
        body = b""
        while True:
            message = await receive()
            body += message.get("body", b"")
            if not message.get("more_body", False):
                break

        try:
            request_data = json.loads(body)
        except json.JSONDecodeError:
            await send_json_response(send, 400, {
                "success": False,
                "error": "Invalid JSON",
                "code": "INVALID_REQUEST",
            })
            return

        # Parse and dispatch
        try:
            request = parse_proxy_request(request_data)
            result = await dispatch_proxy_request(request, session, auth)
            await send_json_response(send, 200, result)
        except ProxyError as e:
            status = 403 if e.code == "UNAUTHORIZED" else 400
            await send_json_response(send, status, {
                "success": False,
                "error": e.message,
                "code": e.code,
            })

    async def app(scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            return

        path = scope["path"]
        method = scope["method"]

        if path == "/health" and method == "GET":
            await handle_health(scope, receive, send)
        elif path == "/sse" and method == "GET":
            await handle_sse(scope, receive, send)
        elif path == "/messages" and method == "POST":
            await handle_messages(scope, receive, send)
        elif path == "/api/v1/proxy" and method == "POST":
            await handle_proxy(scope, receive, send)
        else:
            await handle_not_found(scope, receive, send)

    return app


def _print_mcp_config(external_port: int, tokens: list) -> None:
    """Print Claude Code MCP configuration."""
    print()
    print("Claude Code MCP configuration (copy-paste to add):")
    for t in tokens:
        config = (
            f'{{"type": "sse", "url": "http://localhost:{external_port}/sse", '
            f'"headers": {{"Authorization": "Bearer {t.token}"}}}}'
        )
        print(f"  claude mcp add-json grist-{t.name} '{config}'")
    print()


class UvicornAccessFilter(logging.Filter):
    """Suppress uvicorn access logs unless LOG_LEVEL is DEBUG.

    At INFO level, only grist_mcp tool logs are shown.
    At DEBUG level, all HTTP requests are visible.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        # Only show uvicorn access logs at DEBUG level
        return os.environ.get("LOG_LEVEL", "INFO").upper() == "DEBUG"


def main():
    """Run the SSE server."""
    port = int(os.environ.get("PORT", "3000"))
    external_port = int(os.environ.get("EXTERNAL_PORT", str(port)))
    config_path = os.environ.get("CONFIG_PATH", "/app/config.yaml")

    setup_logging()

    # Suppress uvicorn access logs at INFO level (only show tool logs)
    logging.getLogger("uvicorn.access").addFilter(UvicornAccessFilter())

    if not _ensure_config(config_path):
        return

    config = load_config(config_path)

    print(f"Starting grist-mcp SSE server on port {port}")
    print(f"  SSE endpoint: http://0.0.0.0:{port}/sse")
    print(f"  Messages endpoint: http://0.0.0.0:{port}/messages")

    _print_mcp_config(external_port, config.tokens)

    app = create_app(config)

    # Configure uvicorn logging to reduce health check noise
    log_config = uvicorn.config.LOGGING_CONFIG
    log_config["formatters"]["default"]["fmt"] = "%(message)s"
    log_config["formatters"]["access"]["fmt"] = "%(message)s"

    uvicorn.run(app, host="0.0.0.0", port=port, log_config=log_config)


if __name__ == "__main__":
    main()
