"""Unit tests for logging module."""

import logging

from grist_mcp.logging import truncate_token, extract_stats, format_tool_log


class TestTruncateToken:
    def test_normal_token_shows_prefix_suffix(self):
        token = "abcdefghijklmnop"
        assert truncate_token(token) == "abc...nop"

    def test_short_token_shows_asterisks(self):
        token = "abcdefgh"  # 8 chars
        assert truncate_token(token) == "***"

    def test_very_short_token_shows_asterisks(self):
        token = "abc"
        assert truncate_token(token) == "***"

    def test_empty_token_shows_asterisks(self):
        assert truncate_token("") == "***"

    def test_boundary_token_shows_prefix_suffix(self):
        token = "abcdefghi"  # 9 chars - first to show truncation
        assert truncate_token(token) == "abc...ghi"


class TestExtractStats:
    def test_list_documents(self):
        result = {"documents": [{"name": "a"}, {"name": "b"}, {"name": "c"}]}
        assert extract_stats("list_documents", {}, result) == "3 docs"

    def test_list_tables(self):
        result = {"tables": ["Orders", "Products"]}
        assert extract_stats("list_tables", {}, result) == "2 tables"

    def test_describe_table(self):
        result = {"columns": [{"id": "A"}, {"id": "B"}]}
        assert extract_stats("describe_table", {}, result) == "2 columns"

    def test_get_records(self):
        result = {"records": [{"id": 1}, {"id": 2}]}
        assert extract_stats("get_records", {}, result) == "2 records"

    def test_sql_query(self):
        result = {"records": [{"a": 1}, {"a": 2}, {"a": 3}]}
        assert extract_stats("sql_query", {}, result) == "3 rows"

    def test_add_records_from_args(self):
        args = {"records": [{"a": 1}, {"a": 2}]}
        assert extract_stats("add_records", args, {"ids": [1, 2]}) == "2 records"

    def test_update_records_from_args(self):
        args = {"records": [{"id": 1, "fields": {}}, {"id": 2, "fields": {}}]}
        assert extract_stats("update_records", args, {}) == "2 records"

    def test_delete_records_from_args(self):
        args = {"record_ids": [1, 2, 3]}
        assert extract_stats("delete_records", args, {}) == "3 records"

    def test_create_table(self):
        args = {"columns": [{"id": "A"}, {"id": "B"}]}
        assert extract_stats("create_table", args, {}) == "2 columns"

    def test_single_column_ops(self):
        assert extract_stats("add_column", {}, {}) == "1 column"
        assert extract_stats("modify_column", {}, {}) == "1 column"
        assert extract_stats("delete_column", {}, {}) == "1 column"

    def test_empty_result_returns_zero(self):
        assert extract_stats("list_documents", {}, {"documents": []}) == "0 docs"

    def test_unknown_tool(self):
        assert extract_stats("unknown_tool", {}, {}) == "-"


class TestFormatToolLog:
    def test_success_format(self):
        line = format_tool_log(
            agent_name="dev-agent",
            token="abcdefghijklmnop",
            tool="get_records",
            document="sales",
            stats="42 records",
            status="success",
            duration_ms=125,
        )
        assert "dev-agent" in line
        assert "abc...nop" in line
        assert "get_records" in line
        assert "sales" in line
        assert "42 records" in line
        assert "success" in line
        assert "125ms" in line
        # Check pipe-delimited format
        assert line.count("|") == 6

    def test_no_document(self):
        line = format_tool_log(
            agent_name="dev-agent",
            token="abcdefghijklmnop",
            tool="list_documents",
            document=None,
            stats="3 docs",
            status="success",
            duration_ms=45,
        )
        assert "| - |" in line

    def test_error_format(self):
        line = format_tool_log(
            agent_name="dev-agent",
            token="abcdefghijklmnop",
            tool="add_records",
            document="inventory",
            stats="5 records",
            status="error",
            duration_ms=89,
            error_message="Grist API error: Invalid column 'foo'",
        )
        assert "error" in line
        assert "\n    Grist API error: Invalid column 'foo'" in line


class TestSetupLogging:
    def test_default_level_is_info(self, monkeypatch):
        monkeypatch.delenv("LOG_LEVEL", raising=False)

        from grist_mcp.logging import setup_logging
        setup_logging()

        logger = logging.getLogger("grist_mcp")
        assert logger.level == logging.INFO

    def test_respects_log_level_env(self, monkeypatch):
        monkeypatch.setenv("LOG_LEVEL", "DEBUG")

        from grist_mcp.logging import setup_logging
        setup_logging()

        logger = logging.getLogger("grist_mcp")
        assert logger.level == logging.DEBUG

    def test_invalid_level_defaults_to_info(self, monkeypatch):
        monkeypatch.setenv("LOG_LEVEL", "INVALID")

        from grist_mcp.logging import setup_logging
        setup_logging()

        logger = logging.getLogger("grist_mcp")
        assert logger.level == logging.INFO
