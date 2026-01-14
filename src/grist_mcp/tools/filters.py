"""Filter normalization for Grist API queries."""

from typing import Any


def normalize_filter_value(value: Any) -> list:
    """Ensure a filter value is a list.

    Grist API expects filter values to be arrays.

    Args:
        value: Single value or list of values.

    Returns:
        Value wrapped in list, or original list if already a list.
    """
    if isinstance(value, list):
        return value
    return [value]


def normalize_filter(filter: dict | None) -> dict | None:
    """Normalize filter values to array format for Grist API.

    Grist expects all filter values to be arrays. This function
    wraps single values in lists.

    Args:
        filter: Filter dict with column names as keys.

    Returns:
        Normalized filter dict, or None if input was None.
    """
    if not filter:
        return filter

    return {key: normalize_filter_value(value) for key, value in filter.items()}
