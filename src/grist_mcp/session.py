"""Session token management for HTTP proxy access."""

import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

MAX_TTL_SECONDS = 3600  # 1 hour
DEFAULT_TTL_SECONDS = 300  # 5 minutes


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
        ttl_seconds: int = DEFAULT_TTL_SECONDS,
    ) -> SessionToken:
        """Create a new session token.

        TTL is capped at MAX_TTL_SECONDS (1 hour).
        """
        now = datetime.now(timezone.utc)
        token_str = f"sess_{secrets.token_urlsafe(32)}"

        # Cap TTL at maximum
        effective_ttl = min(ttl_seconds, MAX_TTL_SECONDS)

        session = SessionToken(
            token=token_str,
            document=document,
            permissions=permissions,
            agent_name=agent_name,
            created_at=now,
            expires_at=now + timedelta(seconds=effective_ttl),
        )

        self._tokens[token_str] = session
        return session
