# Judge Q&A

## Why voice?

Market sellers may be serving customers with wet hands and no time to fill
forms. One spoken sentence becomes a structured ledger entry.

## Is the model trusted with money?

No. The service owns validation, conversion, idempotency, and persistence. The
model is an input adapter; the digest model is intended to narrate verified
facts, not calculate them.

## Why append-only records?

Undo creates a compensating reversal. The original row remains available for an
audit trail.

## Why MCP?

MCP exposes typed bookkeeping capabilities to an agent while keeping business
rules inside the service layer.

## What is verified today?

The local MVP, six tests, compilation, and dependency-light MCP listing/call
smoke path are verified. Official SDK transport, live PostgreSQL, external HTTPS,
and Alexa+ registration are not claimed as verified.
