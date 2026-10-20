# Devpost draft

## Inspiration

Informal merchants run on trust and memory. A lost credit note can mean lost
income. BancaVoz gives a market seller a voice-first ledger that works around
busy hands and busy queues.

## What it does

BancaVoz records sales, expenses, credit, payments, summaries, and reversals
through a small bookkeeping service with a browser simulator fallback.

## How we built it

Python, FastAPI, SQLite for local reproducibility, an append-only ledger, integer
minor-unit money, idempotent writes, Docker, and an MCP-compatible adapter. The
service layer remains deterministic and testable without AWS credentials.

## Challenges

Short spoken responses, retry-safe writes, preserving audit history during undo,
and keeping the external language layer separate from financial rules.

## Accomplishments

A runnable open-source MVP with a simulator, tests, Docker packaging, schema,
license, and documented limitations.

## What's next

Complete PostgreSQL hosting and official MCP transport validation, finish the
full credit/digest acceptance suite, add Portuguese speech, and validate Alexa+
registration.
