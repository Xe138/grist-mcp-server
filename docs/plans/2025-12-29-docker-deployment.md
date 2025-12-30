# Docker Deployment Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make grist-mcp deployable via Docker Compose with automated CI builds on version tag pushes.

**Architecture:** Replace stdio transport with SSE (HTTP-based) for remote operation. Multi-stage Dockerfile for small images. Single adaptive CI workflow that detects Gitea vs GitHub and pushes to the appropriate registry.

**Tech Stack:** Python 3.14, Starlette (ASGI), Uvicorn, Docker, GitHub Actions (compatible with Gitea Actions)

---

### Task 1: Add SSE Transport Dependencies

**Files:**
- Modify: `pyproject.toml`

**Step 1: Add dependencies to pyproject.toml**

Edit `pyproject.toml` to add the SSE transport dependencies:

```python
dependencies = [
    "mcp>=1.0.0",
    "httpx>=0.27.0",
    "pyyaml>=6.0",
    "starlette>=0.41.0",
    "uvicorn>=0.32.0",
    "sse-starlette>=2.1.0",
]
```

**Step 2: Sync dependencies**

Run: `uv sync`
Expected: Dependencies install successfully

**Step 3: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "feat: add SSE transport dependencies"
```

---

### Task 2: Implement SSE Transport in main.py

**Files:**
- Modify: `src/grist_mcp/main.py`

**Step 1: Replace main.py with SSE implementation**

Replace the entire contents of `src/grist_mcp/main.py` with:

```python
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
```

**Step 2: Test that the server starts**

Run: `CONFIG_PATH=./config.yaml.example GRIST_MCP_TOKEN=test uv run python -m grist_mcp.main &`
Expected: Server starts, prints port info (will fail auth but that's OK for this test)
Kill: `pkill -f "python -m grist_mcp.main"`

**Step 3: Commit**

```bash
git add src/grist_mcp/main.py
git commit -m "feat: replace stdio with SSE transport"
```

---

### Task 3: Create Dockerfile

**Files:**
- Create: `Dockerfile`

**Step 1: Create multi-stage Dockerfile**

Create `Dockerfile` with:

```dockerfile
# Stage 1: Builder
FROM python:3.14-slim AS builder

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install dependencies
RUN uv sync --frozen --no-dev --no-install-project

# Copy source code
COPY src ./src

# Install the project
RUN uv sync --frozen --no-dev


# Stage 2: Runtime
FROM python:3.14-slim

# Create non-root user
RUN useradd --create-home --shell /bin/bash appuser

WORKDIR /app

# Copy virtual environment from builder
COPY --from=builder /app/.venv /app/.venv

# Copy source code
COPY --from=builder /app/src ./src

# Set environment
ENV PATH="/app/.venv/bin:$PATH"
ENV PORT=3000

# Switch to non-root user
USER appuser

EXPOSE 3000

CMD ["python", "-m", "grist_mcp.main"]
```

**Step 2: Verify Dockerfile syntax**

Run: `docker build --check .` (if available) or just proceed to next step

**Step 3: Commit**

```bash
git add Dockerfile
git commit -m "feat: add multi-stage Dockerfile"
```

---

### Task 4: Create docker-compose.yaml

**Files:**
- Create: `docker-compose.yaml`

**Step 1: Create docker-compose.yaml**

Create `docker-compose.yaml` with:

```yaml
services:
  grist-mcp:
    build: .
    ports:
      - "${PORT:-3000}:3000"
    volumes:
      - ./config.yaml:/app/config.yaml:ro
    env_file:
      - .env
    restart: unless-stopped
```

**Step 2: Commit**

```bash
git add docker-compose.yaml
git commit -m "feat: add docker-compose.yaml"
```

---

### Task 5: Create .env.example

**Files:**
- Create: `.env.example`

**Step 1: Create .env.example**

Create `.env.example` with:

```bash
# grist-mcp environment configuration

# Server port (default: 3000)
PORT=3000

# Agent authentication token (required)
# Generate with: python -c "import secrets; print(secrets.token_urlsafe(32))"
GRIST_MCP_TOKEN=your-agent-token-here

# Grist API keys (referenced in config.yaml)
GRIST_WORK_API_KEY=your-work-api-key
GRIST_PERSONAL_API_KEY=your-personal-api-key

# Optional: Override config path (default: /app/config.yaml)
# CONFIG_PATH=/app/config.yaml
```

**Step 2: Commit**

```bash
git add .env.example
git commit -m "feat: add .env.example template"
```

---

### Task 6: Create CI Workflow

**Files:**
- Create: `.github/workflows/build.yaml`

**Step 1: Create workflow directory**

Run: `mkdir -p .github/workflows`

**Step 2: Create adaptive CI workflow**

Create `.github/workflows/build.yaml` with:

```yaml
name: Build and Push Docker Image

on:
  push:
    tags:
      - 'v*.*.*'

env:
  IMAGE_NAME: grist-mcp

jobs:
  build:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      packages: write

    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Determine registry
        id: registry
        run: |
          if [ "${{ vars.GITEA_ACTIONS }}" = "true" ]; then
            # Gitea: use server URL as registry
            REGISTRY="${{ github.server_url }}"
            REGISTRY="${REGISTRY#https://}"
            REGISTRY="${REGISTRY#http://}"
            echo "registry=${REGISTRY}" >> $GITHUB_OUTPUT
            echo "is_gitea=true" >> $GITHUB_OUTPUT
          else
            # GitHub: use GHCR
            echo "registry=ghcr.io" >> $GITHUB_OUTPUT
            echo "is_gitea=false" >> $GITHUB_OUTPUT
          fi

      - name: Log in to GitHub Container Registry
        if: steps.registry.outputs.is_gitea == 'false'
        uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Log in to Gitea Container Registry
        if: steps.registry.outputs.is_gitea == 'true'
        uses: docker/login-action@v3
        with:
          registry: ${{ steps.registry.outputs.registry }}
          username: ${{ github.actor }}
          password: ${{ secrets.REGISTRY_TOKEN }}

      - name: Extract metadata (tags, labels)
        id: meta
        uses: docker/metadata-action@v5
        with:
          images: ${{ steps.registry.outputs.registry }}/${{ github.repository }}
          tags: |
            type=semver,pattern={{version}}
            type=semver,pattern={{major}}.{{minor}}
            type=semver,pattern={{major}}
            type=raw,value=latest

      - name: Build and push
        uses: docker/build-push-action@v6
        with:
          context: .
          push: true
          tags: ${{ steps.meta.outputs.tags }}
          labels: ${{ steps.meta.outputs.labels }}
          cache-from: type=gha
          cache-to: type=gha,mode=max
```

**Step 3: Commit**

```bash
git add .github/workflows/build.yaml
git commit -m "feat: add CI workflow for Docker builds"
```

---

### Task 7: Update README with Docker Instructions

**Files:**
- Modify: `README.md`

**Step 1: Read current README**

Read `README.md` to understand current structure.

**Step 2: Add Docker section after existing content**

Add a "Docker Deployment" section with:
- Quick start with docker-compose
- Environment variable reference
- Configuration instructions

**Step 3: Commit**

```bash
git add README.md
git commit -m "docs: add Docker deployment instructions"
```

---

### Task 8: Test Docker Build Locally

**Files:**
- None (verification only)

**Step 1: Build the Docker image**

Run: `docker build -t grist-mcp:test .`
Expected: Build completes successfully

**Step 2: Create test config and .env**

Run:
```bash
cp config.yaml.example config.yaml
cp .env.example .env
```

Edit `.env` to set a test token matching one in `config.yaml`.

**Step 3: Test with docker-compose**

Run: `docker compose up -d`
Expected: Container starts

**Step 4: Verify server is running**

Run: `curl -I http://localhost:3000/sse`
Expected: HTTP response (connection may hang waiting for SSE, that's OK)

**Step 5: Clean up**

Run: `docker compose down`

**Step 6: Final commit if any fixes needed**

If any fixes were required, commit them.

---

## Post-Implementation

After all tasks complete:

1. **Tag a version:** `git tag v0.2.0 && git push --tags`
2. **Configure Gitea secret:** Add `REGISTRY_TOKEN` in Gitea repo settings
3. **Verify CI:** Check that workflow runs and pushes images
