"""Authentication and authorization."""

from dataclasses import dataclass
from enum import Enum

from grist_mcp.config import Config, Token


class Permission(Enum):
    """Document permission levels."""
    READ = "read"
    WRITE = "write"
    SCHEMA = "schema"


class AuthError(Exception):
    """Authentication or authorization error."""
    pass


@dataclass
class Agent:
    """An authenticated agent."""
    token: str
    name: str
    _token_obj: Token


class Authenticator:
    """Handles token validation and permission checking."""

    def __init__(self, config: Config):
        self._config = config
        self._token_map = {t.token: t for t in config.tokens}

    def authenticate(self, token: str) -> Agent:
        """Validate token and return Agent object."""
        token_obj = self._token_map.get(token)
        if token_obj is None:
            raise AuthError("Invalid token")

        return Agent(
            token=token,
            name=token_obj.name,
            _token_obj=token_obj,
        )

    def authorize(self, agent: Agent, document: str, permission: Permission) -> None:
        """Check if agent has permission on document. Raises AuthError if not."""
        # Find the scope entry for this document
        scope_entry = None
        for scope in agent._token_obj.scope:
            if scope.document == document:
                scope_entry = scope
                break

        if scope_entry is None:
            raise AuthError("Document not in scope")

        if permission.value not in scope_entry.permissions:
            raise AuthError("Permission denied")

    def get_accessible_documents(self, agent: Agent) -> list[dict]:
        """Return list of documents agent can access with their permissions."""
        return [
            {"name": scope.document, "permissions": scope.permissions}
            for scope in agent._token_obj.scope
        ]

    def get_document(self, document_name: str) -> "Document":
        """Get document config by name.

        Raises:
            AuthError: If document is not configured.
        """
        from grist_mcp.config import Document
        doc = self._config.documents.get(document_name)
        if doc is None:
            raise AuthError(f"Document '{document_name}' not configured")
        return doc
