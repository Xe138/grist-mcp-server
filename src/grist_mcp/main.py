"""Main entry point for the MCP server with SSE transport."""

import os
import sys

import uvicorn
from mcp.server.sse import SseServerTransport
from starlette.applications import Starlette
from starlette.routing import Route

from grist_mcp.server import create_server
from grist_mcp.auth import AuthError


def create_app() -> Starlette:
    """Create the Starlette ASGI application."""
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

    async def handle_sse(request):
        async with sse.connect_sse(
            request.scope, request.receive, request._send
        ) as streams:
            await server.run(
                streams[0], streams[1], server.create_initialization_options()
            )

    async def handle_messages(request):
        await sse.handle_post_message(request.scope, request.receive, request._send)

    return Starlette(
        routes=[
            Route("/sse", endpoint=handle_sse),
            Route("/messages", endpoint=handle_messages, methods=["POST"]),
        ]
    )


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
