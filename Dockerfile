# Stage 1: Builder
FROM python:3.14-slim@sha256:9b81fe9acff79e61affb44aaf3b6ff234392e8ca477cb86c9f7fd11732ce9b6a AS builder

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest@sha256:143b40f4ab56a780f43377604702107b5a35f83a4453daf1e4be691358718a6a /uv /usr/local/bin/uv

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
FROM python:3.14-slim@sha256:9b81fe9acff79e61affb44aaf3b6ff234392e8ca477cb86c9f7fd11732ce9b6a

# Create non-root user
RUN useradd --create-home --shell /bin/bash appuser

WORKDIR /app

# Copy virtual environment from builder
COPY --from=builder --chown=appuser:appuser /app/.venv /app/.venv

# Copy source code
COPY --from=builder --chown=appuser:appuser /app/src ./src

# Set environment
ENV PATH="/app/.venv/bin:$PATH"
ENV PORT=3000

# Switch to non-root user
USER appuser

EXPOSE 3000

CMD ["python", "-m", "grist_mcp.main"]
