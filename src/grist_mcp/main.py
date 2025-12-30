"""Main entry point for the MCP server with SSE transport."""

import os
import sys
from typing import Any

import uvicorn
from mcp.server.sse import SseServerTransport

from grist_mcp.server import create_server
from grist_mcp.auth import AuthError


Scope = dict[str, Any]
Receive = Any
Send = Any


def create_app():
    """Create the ASGI application."""
    config_path = os.environ.get("CONFIG_PATH", "/app/config.yaml")

    if not os.path.exists(config_path):
        print(f"Error: Config file not found at {config_path}", file=sys.stderr)
        sys.exit(1)

    try:
        server = create_server(config_path)
    except AuthError as e:
        print(f"Authentication error: {e}", file=sys.stderr)
        sys.exit(1)

    sse = SseServerTransport("/messages")

    async def handle_sse(scope: Scope, receive: Receive, send: Send) -> None:
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
        else:
            await handle_not_found(scope, receive, send)

    return app


def main():
    """Run the SSE server."""
    port = int(os.environ.get("PORT", "3000"))
    app = create_app()
    print(f"Starting grist-mcp SSE server on port {port}")
    print(f"  SSE endpoint: http://0.0.0.0:{port}/sse")
    print(f"  Messages endpoint: http://0.0.0.0:{port}/messages")
    uvicorn.run(app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
