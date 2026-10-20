# BancaVoz demo script

Target length: under three minutes. This script describes the verified local MVP
path; do not describe Alexa+ or public HTTPS as verified until the deployment
smoke test passes.

| Time | Action | Explanation |
| --- | --- | --- |
| 0:00–0:20 | Show `/sim` | “Market sellers often have no free hands for forms.” |
| 0:20–0:45 | Say “sold 3 bags of rice at 450” | Show the structured sale and tool call. |
| 0:45–1:00 | Repeat the same write key | Explain idempotency and retry safety. |
| 1:00–1:20 | Record an expense | Show the append-only ledger result. |
| 1:20–1:40 | Open summary | Explain integer money and deterministic facts. |
| 1:40–2:00 | Undo the latest entry | Explain reversal instead of destructive deletion. |
| 2:00–2:25 | Show `/mcp` tools/list | Explain the adapter/service separation. |
| 2:25–2:55 | Show GitHub, tests, license, Docker | Close with open-source and reproducibility. |

## Claims to avoid

Do not claim full Alexa+ connectivity, official MCP Streamable HTTP compliance,
PostgreSQL production support, or Bedrock numeric fact-checking until each is
tested and recorded in the runbook.
