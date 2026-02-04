# Stage 1: Builder
FROM python:3.14-slim@sha256:1a3c6dbfd2173971abba880c3cc2ec4643690901f6ad6742d0827bae6cefc925 AS builder

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest@sha256:db9370c2b0b837c74f454bea914343da9f29232035aa7632a1b14dc03add9edb /uv /usr/local/bin/uv

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
FROM python:3.14-slim@sha256:1a3c6dbfd2173971abba880c3cc2ec4643690901f6ad6742d0827bae6cefc925

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
