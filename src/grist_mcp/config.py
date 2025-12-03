"""Configuration loading and parsing."""

import os
import re
from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass
class Document:
    """A Grist document configuration."""
    url: str
    doc_id: str
    api_key: str


@dataclass
class TokenScope:
    """Access scope for a single document."""
    document: str
    permissions: list[str]


@dataclass
class Token:
    """An agent token with its access scopes."""
    token: str
    name: str
    scope: list[TokenScope]


@dataclass
class Config:
    """Full server configuration."""
    documents: dict[str, Document]
    tokens: list[Token]


def _substitute_env_vars(value: str) -> str:
    """Replace ${VAR} patterns with environment variable values."""
    pattern = r'\$\{([^}]+)\}'

    def replacer(match: re.Match) -> str:
        var_name = match.group(1)
        env_value = os.environ.get(var_name)
        if env_value is None:
            raise ValueError(f"Environment variable not set: {var_name}")
        return env_value

    return re.sub(pattern, replacer, value)


def _substitute_env_vars_recursive(obj):
    """Recursively substitute env vars in a data structure."""
    if isinstance(obj, str):
        return _substitute_env_vars(obj)
    elif isinstance(obj, dict):
        return {k: _substitute_env_vars_recursive(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_substitute_env_vars_recursive(item) for item in obj]
    return obj


def load_config(config_path: str) -> Config:
    """Load and parse configuration from YAML file."""
    path = Path(config_path)
    raw = yaml.safe_load(path.read_text())

    # Substitute environment variables
    raw = _substitute_env_vars_recursive(raw)

    # Parse documents
    documents = {}
    for name, doc_data in raw.get("documents", {}).items():
        documents[name] = Document(
            url=doc_data["url"],
            doc_id=doc_data["doc_id"],
            api_key=doc_data["api_key"],
        )

    # Parse tokens
    tokens = []
    for token_data in raw.get("tokens", []):
        scope = [
            TokenScope(
                document=s["document"],
                permissions=s["permissions"],
            )
            for s in token_data.get("scope", [])
        ]
        tokens.append(Token(
            token=token_data["token"],
            name=token_data["name"],
            scope=scope,
        ))

    return Config(documents=documents, tokens=tokens)
