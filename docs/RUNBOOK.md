# Runbook

## Verified local commands

Evidence captured on 2026-10-20 in Python 3.15 on Windows:

| Command | Output |
| --- | --- |
| `python -m pytest -q` | `20 passed` |
| `python -m pytest --cov=bancavoz --cov-report=term-missing -q` | `20 passed`; `TOTAL 590 177 70%` |
| `python -m ruff check .` | `All checks passed!` |
| `python -m mypy bancavoz` | `Success: no issues found in 9 source files` |
| `python scripts/generate_mcp_tools_doc.py` | `generated docs/MCP_TOOLS.md from 10 tools` |
| `git grep` credential-pattern scan | `secret-scan: no credential-pattern matches` |

The MCP script also recorded HTTP 200 for `initialize` and `tools/list`, with
10 tools returned. The local test suite uses the official SDK route at
`/mcp/`; `/mcp-legacy` is a separate compatibility endpoint.

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
- `BANCAVOZ_DATABASE_URL`: currently must be a `sqlite:///...` URL.
- `BANCAVOZ_CURRENCY`: optional currency label, default `MZN`.
- `BANCAVOZ_BEDROCK_MODEL_ID` and AWS credentials: optional and not verified in deployment.

## Hosted deployment status

No Fly.io, Render, or other public deployment has been run in this task. There
is no public URL, external smoke output, rollback command, managed Postgres
validation, or production migration run to record. Do not present those as
completed.

The requested production runbook is blocked on implementing a PostgreSQL
adapter and migration runner, adding managed Postgres, deploying to a named
host, and recording `/healthz`, `/readyz`, `/summary`, and `/mcp/` output from
the public URL. No verified rollback procedure is claimed here.
