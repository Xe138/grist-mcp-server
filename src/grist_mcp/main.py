"""Main entry point for the MCP server."""

import asyncio
import os
import sys

from mcp.server.stdio import stdio_server

from grist_mcp.server import create_server
from grist_mcp.auth import AuthError


async def main():
    config_path = os.environ.get("CONFIG_PATH", "/app/config.yaml")

    if not os.path.exists(config_path):
        print(f"Error: Config file not found at {config_path}", file=sys.stderr)
        sys.exit(1)

    try:
        server = create_server(config_path)
    except AuthError as e:
        print(f"Authentication error: {e}", file=sys.stderr)
        sys.exit(1)

    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
