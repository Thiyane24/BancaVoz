# BancaVoz

BancaVoz is a self-contained Python 3.12 MVP for voice-first merchant bookkeeping.

## Run locally

```powershell
py -m venv .venv
.venv\Scripts\python -m pip install -e ".[dev]"
$env:BANCAVOZ_BEARER_TOKEN="dev-token"
uvicorn bancavoz.api:app --reload
```

Open `/docs` for the API and `/sim` for the deterministic simulator fallback.
All money is converted to integer minor units at the service boundary. Entries are
append-only and idempotent per merchant and key. SQLite is the default test/local
backend; `bancavoz/db.py` keeps the schema portable and the service isolated from
the database implementation. The optional `mcp` and `bedrock` extras activate
those integrations when installed/configured.

## Endpoints

`GET /healthz` is public. Other API routes require
`Authorization: Bearer $BANCAVOZ_BEARER_TOKEN`. The JSON-RPC-compatible `POST /mcp`
supports `tools/list` and `tools/call`; the optional pinned MCP extra can be used
for SDK-native hosting.

## Current deployment boundary

The checked-in app is fully runnable locally and in Docker with SQLite. A hosted
release still needs a Postgres `DATABASE_URL`, HTTPS termination, and installation
of the optional MCP/Bedrock extras. The deterministic simulator does not require
AWS credentials.

## Seed

`bancavoz-seed` inserts a small demo ledger.
