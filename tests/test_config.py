import pytest
from grist_mcp.config import load_config, Config, Document, Token, TokenScope


def test_load_config_parses_documents(tmp_path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text("""
documents:
  my-doc:
    url: https://grist.example.com
    doc_id: abc123
    api_key: secret-key

tokens: []
""")

    config = load_config(str(config_file))

    assert "my-doc" in config.documents
    doc = config.documents["my-doc"]
    assert doc.url == "https://grist.example.com"
    assert doc.doc_id == "abc123"
    assert doc.api_key == "secret-key"


def test_load_config_parses_tokens(tmp_path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text("""
documents:
  budget:
    url: https://grist.example.com
    doc_id: abc123
    api_key: key123

tokens:
  - token: my-secret-token
    name: test-agent
    scope:
      - document: budget
        permissions: [read, write]
""")

    config = load_config(str(config_file))

    assert len(config.tokens) == 1
    token = config.tokens[0]
    assert token.token == "my-secret-token"
    assert token.name == "test-agent"
    assert len(token.scope) == 1
    assert token.scope[0].document == "budget"
    assert token.scope[0].permissions == ["read", "write"]


def test_load_config_substitutes_env_vars(tmp_path, monkeypatch):
    monkeypatch.setenv("TEST_API_KEY", "env-secret-key")

    config_file = tmp_path / "config.yaml"
    config_file.write_text("""
documents:
  my-doc:
    url: https://grist.example.com
    doc_id: abc123
    api_key: ${TEST_API_KEY}

tokens: []
""")

    config = load_config(str(config_file))

    assert config.documents["my-doc"].api_key == "env-secret-key"


def test_load_config_raises_on_missing_env_var(tmp_path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text("""
documents:
  my-doc:
    url: https://grist.example.com
    doc_id: abc123
    api_key: ${MISSING_VAR}

tokens: []
""")

    with pytest.raises(ValueError, match="MISSING_VAR"):
        load_config(str(config_file))
