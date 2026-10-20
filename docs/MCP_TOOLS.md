# MCP tool contract

The `/mcp` endpoint accepts JSON-RPC requests with bearer authentication.
`tools/list` exposes the available tools and `tools/call` executes them against
the authenticated merchant. Every successful result contains `speech` and `data`.

| Tool | Required arguments |
| --- | --- |
| `log_sale` | `item`, `quantity`, `unit_price`, `idempotency_key` |
| `log_expense` | `description`, `amount`, `idempotency_key` |
| `record_credit_payment` | `customer`, `amount`, `idempotency_key` |
| `get_credit_owed` | none |
| `get_daily_summary` | none |
| `undo_last_entry` | `entry_id`, `idempotency_key` |

The optional `mcp==1.2.0` extra contains the official SDK integration helpers.
The built-in endpoint remains available as a dependency-light local smoke-test
surface.
