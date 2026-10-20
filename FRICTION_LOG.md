# Friction log

- The brief was supplied without a readable attachment in the workspace, so this MVP
  follows the explicit requirements in the request and favors a small, runnable API.
- PostgreSQL was not available for validation. SQLite is used for tests and local runs;
  the schema uses portable SQL and the service has a database boundary for a future
  psycopg adapter.
- MCP SDK APIs vary by release. The optional integration is import-safe and exposes
  tools through `FastMCP` when the pinned SDK provides it.
