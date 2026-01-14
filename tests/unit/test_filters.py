"""Unit tests for filter normalization."""

import pytest

from grist_mcp.tools.filters import normalize_filter, normalize_filter_value


class TestNormalizeFilterValue:
    """Tests for normalize_filter_value function."""

    def test_int_becomes_list(self):
        assert normalize_filter_value(5) == [5]

    def test_string_becomes_list(self):
        assert normalize_filter_value("foo") == ["foo"]

    def test_float_becomes_list(self):
        assert normalize_filter_value(3.14) == [3.14]

    def test_list_unchanged(self):
        assert normalize_filter_value([1, 2, 3]) == [1, 2, 3]

    def test_empty_list_unchanged(self):
        assert normalize_filter_value([]) == []

    def test_single_item_list_unchanged(self):
        assert normalize_filter_value([42]) == [42]

    def test_mixed_type_list_unchanged(self):
        assert normalize_filter_value([1, "foo", 3.14]) == [1, "foo", 3.14]


class TestNormalizeFilter:
    """Tests for normalize_filter function."""

    def test_none_returns_none(self):
        assert normalize_filter(None) is None

    def test_empty_dict_returns_empty_dict(self):
        assert normalize_filter({}) == {}

    def test_single_int_value_wrapped(self):
        result = normalize_filter({"Transaction": 44})
        assert result == {"Transaction": [44]}

    def test_single_string_value_wrapped(self):
        result = normalize_filter({"Status": "active"})
        assert result == {"Status": ["active"]}

    def test_list_value_unchanged(self):
        result = normalize_filter({"Transaction": [44, 45, 46]})
        assert result == {"Transaction": [44, 45, 46]}

    def test_mixed_columns_all_normalized(self):
        """Both ref and non-ref columns are normalized to arrays."""
        result = normalize_filter({
            "Transaction": 44,  # Ref column (int)
            "Debit": 500,       # Non-ref column (int)
            "Memo": "test",     # Non-ref column (str)
        })
        assert result == {
            "Transaction": [44],
            "Debit": [500],
            "Memo": ["test"],
        }

    def test_multiple_values_list_unchanged(self):
        """Filter with multiple values passes through."""
        result = normalize_filter({
            "Status": ["pending", "active"],
            "Priority": [1, 2, 3],
        })
        assert result == {
            "Status": ["pending", "active"],
            "Priority": [1, 2, 3],
        }

    def test_mixed_single_and_list_values(self):
        """Mix of single values and lists."""
        result = normalize_filter({
            "Transaction": 44,            # Single int
            "Status": ["open", "closed"],  # List
            "Amount": 100.50,             # Single float
        })
        assert result == {
            "Transaction": [44],
            "Status": ["open", "closed"],
            "Amount": [100.50],
        }
