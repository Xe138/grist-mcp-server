"""Session token management for HTTP proxy access."""

import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone


@dataclass
class SessionToken:
    """A short-lived session token for proxy access."""
    token: str
    document: str
    permissions: list[str]
    agent_name: str
    created_at: datetime
    expires_at: datetime


class SessionTokenManager:
    """Manages creation and validation of session tokens."""

    def __init__(self):
        self._tokens: dict[str, SessionToken] = {}

    def create_token(
        self,
        agent_name: str,
        document: str,
        permissions: list[str],
        ttl_seconds: int,
    ) -> SessionToken:
        """Create a new session token."""
        now = datetime.now(timezone.utc)
        token_str = f"sess_{secrets.token_urlsafe(32)}"

        session = SessionToken(
            token=token_str,
            document=document,
            permissions=permissions,
            agent_name=agent_name,
            created_at=now,
            expires_at=now + timedelta(seconds=ttl_seconds),
        )

        self._tokens[token_str] = session
        return session
