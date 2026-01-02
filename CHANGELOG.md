# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Session token proxy: agents can request short-lived tokens for bulk operations
- `get_proxy_documentation` MCP tool: returns complete proxy API spec
- `request_session_token` MCP tool: creates scoped session tokens
- `POST /api/v1/proxy` HTTP endpoint: accepts session tokens for direct API access

## [1.0.0] - 2026-01-01

Initial release of grist-mcp, an MCP server for AI agents to interact with Grist spreadsheets.

### Added

#### Core Features
- **MCP Server**: Full Model Context Protocol implementation with SSE transport
- **Token-based Authentication**: Secure agent authentication via `GRIST_MCP_TOKEN`
- **Granular Permissions**: Per-document access control with `read`, `write`, and `schema` scopes
- **Multi-tenant Support**: Configure multiple Grist instances and documents

#### Discovery Tools
- `list_documents`: List accessible documents with their permissions

#### Read Tools
- `list_tables`: List all tables in a document
- `describe_table`: Get column metadata (id, type, formula)
- `get_records`: Fetch records with optional filter, sort, and limit
- `sql_query`: Execute read-only SELECT queries

#### Write Tools
- `add_records`: Insert new records into a table
- `update_records`: Modify existing records by ID
- `delete_records`: Remove records by ID

#### Schema Tools
- `create_table`: Create new tables with column definitions
- `add_column`: Add columns to existing tables
- `modify_column`: Change column type or formula
- `delete_column`: Remove columns from tables

#### Infrastructure
- **Docker Support**: Multi-stage Dockerfile with non-root user
- **Docker Compose**: Ready-to-deploy configuration with environment variables
- **Health Endpoint**: `/health` for container orchestration readiness checks
- **SSE Transport**: Server-Sent Events for MCP client communication
- **Environment Variable Substitution**: `${VAR}` syntax in config files

#### Testing
- **Unit Tests**: Comprehensive coverage with pytest-httpx mocking
- **Integration Tests**: Docker-based tests with ephemeral containers
- **Rich Test Runner**: Progress display for test execution
- **Test Isolation**: Dynamic port discovery for parallel test runs

#### Developer Experience
- **Makefile**: Commands for testing, building, and deployment
- **Dev Environment**: Docker Compose setup for local development
- **MCP Config Display**: Startup message with client configuration snippet

### Security
- SQL injection prevention with SELECT-only query validation
- API key isolation per document
- Token validation at startup (no runtime exposure)
- Non-root container execution
