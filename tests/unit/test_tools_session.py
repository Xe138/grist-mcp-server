import pytest
from grist_mcp.tools.session import get_proxy_documentation


@pytest.mark.asyncio
async def test_get_proxy_documentation_returns_complete_spec():
    result = await get_proxy_documentation()

    assert "description" in result
    assert "endpoint" in result
    assert result["endpoint"] == "POST /api/v1/proxy"
    assert "authentication" in result
    assert "methods" in result
    assert "add_records" in result["methods"]
    assert "get_records" in result["methods"]
    assert "example_script" in result
