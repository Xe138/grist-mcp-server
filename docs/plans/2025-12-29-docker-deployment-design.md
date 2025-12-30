# Docker Deployment Design

## Overview

Make grist-mcp deployable via Docker Compose with CI workflows for automated image builds on version tag pushes.

## Requirements

- Docker Compose for local deployment
- Single CI workflow that works on both Gitea and GitHub
- SSE transport (replacing stdio) for remote server operation
- Port 3000 default, configurable via environment variable
- Python 3.14
- Semantic version tagging (1.2.3, 1.2, 1, latest)
- Config mounted at runtime (not baked into image)

## Files to Create

### Dockerfile

Multi-stage build:

**Stage 1 (builder):**
- Base: `python:3.14-slim`
- Install uv
- Copy `pyproject.toml` and `uv.lock`
- Install dependencies

**Stage 2 (runtime):**
- Base: `python:3.14-slim`
- Copy virtual environment from builder
- Copy source code
- Non-root user (`appuser`) for security
- Expose port 3000
- CMD: run server via uv

### docker-compose.yaml

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

### .env.example

```
PORT=3000
GRIST_MCP_TOKEN=your-agent-token-here
```

### .github/workflows/build.yaml

Single workflow that detects platform (Gitea vs GitHub) at runtime:

- **Trigger:** Push of version tags (`v*.*.*`)
- **Platform detection:** Check `GITEA_ACTIONS` environment variable
- **Registry:**
  - Gitea: `${{ github.server_url }}/${{ github.repository }}`
  - GitHub: `ghcr.io/${{ github.repository }}`
- **Authentication:**
  - Gitea: `${{ secrets.REGISTRY_TOKEN }}`
  - GitHub: `${{ secrets.GITHUB_TOKEN }}`
- **Tags generated:** `1.2.3`, `1.2`, `1`, `latest`

## Files to Modify

### pyproject.toml

Add dependencies:
- `starlette` - ASGI framework for SSE
- `uvicorn` - ASGI server
- `sse-starlette` - SSE support

### src/grist_mcp/main.py

Replace stdio transport with SSE:

1. Create Starlette ASGI app with routes:
   - `GET /sse` - SSE connection endpoint
   - `POST /messages` - Client message endpoint
2. Run with uvicorn on configurable port (default 3000)
3. Keep existing config/auth flow unchanged

### .gitignore

Ensure `.env` is ignored.

## Implementation Order

1. Update dependencies and main.py for SSE transport
2. Create Dockerfile
3. Create docker-compose.yaml and .env.example
4. Create CI workflow
5. Test locally with `docker compose up`

## Secrets to Configure

- **Gitea:** Create `REGISTRY_TOKEN` secret with registry push access
- **GitHub:** Uses automatic `GITHUB_TOKEN`
