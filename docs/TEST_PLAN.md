# Test plan

The local suite covers:

- integer minor-unit conversion and idempotent ledger writes;
- merchant isolation, bearer authentication, and health checks;
- simulator sale handling;
- package compilation;
- MCP `tools/list` and `tools/call` smoke behavior.

Run `python -m pytest -q` and `python -m compileall -q bancavoz`.
Live Postgres, HTTPS, and Alexa+ checks are deployment acceptance checks.
