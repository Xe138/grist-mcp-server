#!/bin/bash
# scripts/run-integration-tests.sh
# Run integration tests with branch isolation and dynamic port discovery
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Get branch-based instance ID
TEST_INSTANCE_ID=$("$SCRIPT_DIR/get-test-instance-id.sh")
export TEST_INSTANCE_ID

echo "Test instance ID: $TEST_INSTANCE_ID"

# Start containers
cd "$PROJECT_ROOT/deploy/test"
docker compose up -d --build --wait

# Discover dynamic ports
GRIST_MCP_PORT=$(docker compose port grist-mcp 3000 | cut -d: -f2)
MOCK_GRIST_PORT=$(docker compose port mock-grist 8484 | cut -d: -f2)

echo "grist-mcp available at: http://localhost:$GRIST_MCP_PORT"
echo "mock-grist available at: http://localhost:$MOCK_GRIST_PORT"

# Export for tests
export GRIST_MCP_URL="http://localhost:$GRIST_MCP_PORT"
export MOCK_GRIST_URL="http://localhost:$MOCK_GRIST_PORT"

# Run tests
cd "$PROJECT_ROOT"
TEST_EXIT=0
uv run pytest tests/integration/ -v || TEST_EXIT=$?

# Cleanup
cd "$PROJECT_ROOT/deploy/test"
docker compose down -v

exit $TEST_EXIT
