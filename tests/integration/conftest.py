"""Fixtures for integration tests."""

import time

import httpx
import pytest
from mcp import ClientSession
from mcp.client.sse import sse_client


GRIST_MCP_URL = "http://localhost:3000"
MOCK_GRIST_URL = "http://localhost:8484"
MAX_WAIT_SECONDS = 30


def wait_for_service(url: str, timeout: int = MAX_WAIT_SECONDS) -> bool:
    """Wait for a service to become healthy."""
    start = time.time()
    while time.time() - start < timeout:
        try:
            response = httpx.get(f"{url}/health", timeout=2.0)
            if response.status_code == 200:
                return True
        except httpx.RequestError:
            pass
        time.sleep(0.5)
    return False


@pytest.fixture(scope="session")
def services_ready():
    """Ensure both services are healthy before running tests."""
    if not wait_for_service(MOCK_GRIST_URL):
        pytest.fail(f"Mock Grist server not ready at {MOCK_GRIST_URL}")
    if not wait_for_service(GRIST_MCP_URL):
        pytest.fail(f"grist-mcp server not ready at {GRIST_MCP_URL}")
    return True


@pytest.fixture
async def mcp_client(services_ready):
    """Create an MCP client connected to grist-mcp via SSE."""
    async with sse_client(f"{GRIST_MCP_URL}/sse") as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            yield session


@pytest.fixture
def mock_grist_client(services_ready):
    """HTTP client for interacting with mock Grist test endpoints."""
    with httpx.Client(base_url=MOCK_GRIST_URL, timeout=10.0) as client:
        yield client


@pytest.fixture(autouse=True)
def clear_mock_grist_log(mock_grist_client):
    """Clear the mock Grist request log before each test."""
    mock_grist_client.post("/_test/requests/clear")
    yield
