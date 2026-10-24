# Stage 1: Builder
FROM python:3.15-slim@sha256:533b0b2f9b5d46fd097091cf826f27902f1d6c3bca714b6dc74551356aa97a51 AS builder

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest@sha256:c4f5de312ee66d46810635ffc5df34a1973ba753e7241ce3a08ef979ddd7bea5 /uv /usr/local/bin/uv

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
FROM python:3.15-slim@sha256:533b0b2f9b5d46fd097091cf826f27902f1d6c3bca714b6dc74551356aa97a51

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
