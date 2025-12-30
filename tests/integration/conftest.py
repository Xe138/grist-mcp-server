"""Fixtures for integration tests."""

import time

import httpx
import pytest


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
