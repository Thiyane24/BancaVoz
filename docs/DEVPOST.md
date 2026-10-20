# Devpost draft

## Inspiration

BancaVoz comes from Mozambique, where informal market sellers often manage
sales and customer credit while serving people with both hands occupied. A
short voice interaction can preserve a credit note without forcing a seller
through a form.

## What it does

BancaVoz records sales, expenses, credit, payments, summaries, and reversals
through a small bookkeeping service with a browser simulator and an official
MCP tools endpoint.

## How we built it

Python, FastAPI, SQLite for local reproducibility, integer minor-unit money,
idempotent writes, Docker, and the MCP Python SDK. Financial facts are
calculated by the service layer; the current verified summary path uses a
deterministic template. Bedrock is not claimed as deployed or verified.

## Impact

The intended impact is fewer lost credit notes, safer retries, and more
accessible bookkeeping for informal sellers.

## Accomplishments

The local suite passes 20 tests; Ruff and mypy pass; the official MCP
initialize/tools-list smoke path returns HTTP 200 and 10 tools; the repository
is public and reproducible locally.

## What's next

Implement and verify PostgreSQL migrations and hosted deployment, complete the
six-utterance simulator contract, add rate limiting and merchant token
storage, and finish the Bedrock Converse digest validation/cache path.
