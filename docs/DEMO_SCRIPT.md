# BancaVoz demo script

This is the local simulator story targeted under three minutes. It has not
been run against a public URL.

| Time | Utterance/action | What to explain |
| --- | --- | --- |
| 0:00–0:20 | Open `/sim` | Voice-first bookkeeping for Mozambique market sellers. |
| 0:20–0:40 | “sold 2 rice at 10” | Sale becomes a typed ledger write. |
| 0:40–1:00 | “Maria owes half” | Not yet verified in the simulator; do not claim it works. |
| 1:00–1:20 | “Maria paid 5” | Not yet verified end-to-end; payment parsing is fixed to Maria. |
| 1:20–1:35 | “undo that” | Append-only reversal rather than deletion. |
| 1:35–1:55 | “spent 200 on transport” | Category parsing is not yet verified. |
| 1:55–2:15 | “how did today go” | Deterministic summary facts and template speech. |
| 2:15–2:35 | “end of day digest” | Dedicated digest flow is not yet verified. |
| 2:35–2:55 | Show tests and MCP tools list | Explain reproducible evidence and gaps. |

Only the sale, undo, summary, and local MCP tools-list portions have passing
evidence. Complete and test the six-utterance contract before presenting it as
fully verified.
