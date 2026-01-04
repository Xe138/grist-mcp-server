# Stage 1: Builder
FROM python:3.14-slim@sha256:3955a7dd66ccf92b68d0232f7f86d892eaf75255511dc7e98961bdc990dc6c9b AS builder

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest@sha256:15f68a476b768083505fe1dbfcc998344d0135f0ca1b8465c4760b323904f05a /uv /usr/local/bin/uv

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
FROM python:3.14-slim@sha256:3955a7dd66ccf92b68d0232f7f86d892eaf75255511dc7e98961bdc990dc6c9b

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
