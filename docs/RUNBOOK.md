# Runbook

## Verified local commands

Evidence captured on 2026-10-20 in Python 3.15 on Windows:

| Command | Output |
| --- | --- |
| `python -m pytest -q` | `36 passed` |
| `python -m pytest --cov=bancavoz --cov-report=term-missing -q` | `34 passed`; `TOTAL 721 157 78%` |
| `python -m ruff check .` | `All checks passed!` |
| `python -m mypy bancavoz` | `Success: no issues found in 9 source files` |
| `python -m pip check` | `No broken requirements found.` |
| Tailwind CLI build | `bancavoz/web/static/tailwind.css` generated successfully |
| `python scripts/generate_mcp_tools_doc.py` | `generated docs/MCP_TOOLS.md from 10 tools` |
| `git grep` credential-pattern scan | `secret-scan: no credential-pattern matches` |

The MCP script also recorded HTTP 200 for `initialize` and `tools/list`, with
10 tools returned. The local test suite uses the official SDK routes at both
`/mcp` and `/mcp/`.

The local Bandit installation could not complete on Windows/Python 3.15 because
PyYAML requires Microsoft Visual C++ 14.0; CI should run the declared security
tools on Ubuntu. Docker Desktop was also unavailable locally, so image build
and hosted smoke output remain unverified here.

## Local deployment

```powershell
Copy-Item .env.example .env
# Edit .env and replace the development token.
docker compose up --build
docker compose exec bancavoz bancavoz-seed
Invoke-WebRequest http://localhost:8000/healthz
Invoke-WebRequest http://localhost:8000/readyz
```

Required secrets/configuration:

- `BANCAVOZ_BEARER_TOKEN`: required bearer token; never use `dev-token` in production.
- `BANCAVOZ_DATABASE_URL`: `postgresql://...` in production; SQLite is for tests/local use.
- `BANCAVOZ_CURRENCY`: optional currency label, default `MZN`.
- `BANCAVOZ_BEDROCK_MODEL_ID` and AWS credentials: optional and not verified in deployment.

## Hosted deployment status

No Fly.io, Render, or other public deployment has been run in this task. There
is no public URL, external smoke output, rollback command, managed Postgres
validation, or production migration run to record. Do not present those as
completed.

The application-side production blockers are implemented. A public deployment
and external smoke run are still required before claiming production operation.

## Render deployment and rollback

1. Push `main` to GitHub.
2. In Render, choose **New > Blueprint**, select this repository, and apply
   `render.yaml`.
3. Set `BANCAVOZ_BEARER_TOKEN` to a long random secret. Never use `dev-token`.
4. Wait for `/healthz`, then run `/readyz`, authenticated `/summary`, and one
   authenticated write with a fresh idempotency key.
5. Save the public URL and raw outputs in this file.
6. To roll back, select the previous successful Render deploy and choose
   **Rollback**, then re-run `/healthz`, `/readyz`, and `/summary`.
