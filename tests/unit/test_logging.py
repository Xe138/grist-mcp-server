"""Unit tests for logging module."""

from grist_mcp.logging import truncate_token


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
