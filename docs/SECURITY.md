# Security status

## Verified

- Bearer authentication is required on protected HTTP and official MCP routes.
- Token comparison uses `hmac.compare_digest`.
- Production requests are rejected when the configured token is still
  `dev-token`.
- Responses include `X-Content-Type-Options`, `X-Frame-Options`, a basic CSP,
  and an `X-Request-ID` response header.
- SQL is parameterized in the SQLite adapter.
- The HTML form `POST /simulator` was removed; the simulator uses JSON
  `POST /sim/utterance`.
- A repository credential-pattern scan returned
  `secret-scan: no credential-pattern matches`.

Evidence: `python -m pytest tests/test_api.py -q`,
`python -m mypy bancavoz`, and the scan recorded in `RUNBOOK.md`.

## Not implemented or not verified

- Authentication still maps the configured token to one literal merchant ID;
  there is no merchants table or hashed token directory.
- No request rate limiter is implemented.
- Request IDs are response headers only; structured JSON request logging is not
  implemented.
- CSP has not been browser-audited.
- PostgreSQL, hosted secret storage, HTTPS, dependency audit, and external
  penetration testing were not run.

Never commit `.env`, AWS credentials, or production tokens.
