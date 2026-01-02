"""Unit tests for logging module."""

from grist_mcp.logging import truncate_token, extract_stats


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
