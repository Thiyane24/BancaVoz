# MCP tool contract

The `/mcp` endpoint is served by the pinned official MCP Python SDK using
Streamable HTTP and bearer authentication. `tools/list` exposes the available
tools and `tools/call` executes them against the authenticated demo merchant.
Every successful result contains `speech` and `data`.

| Tool | Required arguments |
| --- | --- |
| `log_sale` | `item`, `quantity`, `unit_price`, `idempotency_key` |
| `log_expense` | `description`, `amount`, `idempotency_key` |
| `record_credit_payment` | `customer`, `amount`, `idempotency_key` |
| `get_credit_owed` | none |
| `get_daily_summary` | none |
| `undo_last_entry` | `entry_id`, `idempotency_key` |
| `get_top_sellers` | optional `day`, `limit` |
| `set_stock` | `item`, `quantity`, optional `low_at` |
| `check_low_stock` | none |
| `get_daily_digest` | optional `day`, `refresh` |

The exact SDK pin is `mcp==1.30.0`. The old dependency-light JSON-RPC handler is
retained at `/mcp-legacy` only for compatibility; `/mcp` is the official route.
