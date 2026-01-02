"""Logging configuration and utilities."""


def truncate_token(token: str) -> str:
    """Truncate token to show first 3 and last 3 chars.

    Tokens 8 chars or shorter show *** for security.
    """
    if len(token) <= 8:
        return "***"
    return f"{token[:3]}...{token[-3:]}"
