import pytest
from grist_mcp.proxy import parse_proxy_request, ProxyRequest, ProxyError


def test_parse_proxy_request_valid_add_records():
    body = {
        "method": "add_records",
        "table": "Orders",
        "records": [{"item": "Widget", "qty": 10}],
    }

    request = parse_proxy_request(body)

    assert request.method == "add_records"
    assert request.table == "Orders"
    assert request.records == [{"item": "Widget", "qty": 10}]


def test_parse_proxy_request_missing_method():
    body = {"table": "Orders"}

    with pytest.raises(ProxyError) as exc_info:
        parse_proxy_request(body)

    assert exc_info.value.code == "INVALID_REQUEST"
    assert "method" in str(exc_info.value)
