# Security status

## Verified

- Bearer authentication is required on protected HTTP and official MCP routes.
- Token comparison uses `hmac.compare_digest`.
- Production requests are rejected when the configured token is still
  `dev-token`.
- Merchant tokens are stored as SHA-256 hashes in the `merchants` table and
  resolve to a merchant ID before ledger access.
- Requests are rate-limited per client address and return standard rate headers.
- Requests are emitted as structured JSON log records with a request ID.
- Responses include `X-Content-Type-Options`, `X-Frame-Options`, a basic CSP,
  and an `X-Request-ID` response header.
- SQL is parameterized in the SQLite adapter.
- The HTML form `POST /simulator` was removed; the simulator uses JSON
  `POST /sim/utterance`.
- A repository credential-pattern scan returned
  `secret-scan: no credential-pattern matches`.

Evidence: `python -m pytest tests/test_api.py -q`,
`python -m mypy bancavoz`, and the scan recorded in `RUNBOOK.md`.

## Remaining operational verification

- PostgreSQL adapter and migrations are implemented, but a hosted database
  smoke run must still be recorded for the deployed URL.
- The in-process rate limiter is safe for one web process; use a shared gateway
  or Redis-backed limiter when running multiple replicas.
- CSP has not been browser-audited.
- External penetration testing and the first hosted dependency audit remain
  deployment-owner responsibilities.

Never commit `.env`, AWS credentials, or production tokens.
