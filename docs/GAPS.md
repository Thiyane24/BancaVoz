# Requirement status

This table records the current repository status. “Partial” means there is a
local approximation but not the complete acceptance behavior from the brief.

| ID | Status | Evidence / remaining work |
| --- | --- | --- |
| FR-1 | Done | Official MCP SDK Streamable HTTP is mounted at `/mcp`; local initialize/tools-list smoke test passes. |
| FR-2 | Done | Official SDK generates typed tool schemas; local tools-list smoke test covers all 10 tools. |
| FR-3 | Partial | Sales and ledger work; unit price, paid amount, and half-credit parsing need completion. |
| FR-4 | Done | Expense route and service exist. |
| FR-5 | Partial | Payments and basic overpay validation exist; full customer ledger rules need completion. |
| FR-6 | Partial | Basic credit balance query exists; normalized/ambiguous customer matching is pending. |
| FR-7 | Partial | Summary exists but is not fully date/timezone bounded. |
| FR-8 | Partial | Undo-last and reversal linkage exist; complete stock/credit restoration needs validation. |
| FR-9 | Partial | Top sellers exist by quantity, not all requested revenue periods. |
| FR-10 | Partial | Local set-stock and low-stock service/tools exist; persistent production schema parity is pending. |
| FR-11 | Partial | Template/optional Bedrock digest exists; comparison, cache, and numeric gate are pending. |
| FR-12 | Partial | Same-key idempotency exists; conflicting payload detection needs request hashes. |
| FR-13 | Missing | Case/accent normalization and ambiguity responses need implementation. |
| FR-14 | Partial | Basic item storage exists; normalization rules need formalization. |
| FR-15 | Partial | Structured responses exist; all tool speech length needs a dedicated test. |
| FR-16 | Partial | Some validation errors are speakable; all adapters need consistent error envelopes. |
| FR-17 | Partial | `/sim` supports text/mic and deterministic patterns; complete six-step script is pending. |
| FR-18 | Missing | Narrative numeric fact-check gate is not yet verified. |
| FR-19 | Missing | Digest cache/invalidation is not yet verified. |
| FR-20 | Partial | Seed utility exists; week-long demo dataset needs completion. |
| NFR-1 | Missing | No latency benchmark has been run. |
| NFR-2 | Partial | Service stores integer minor units; request models still accept floats. |
| NFR-3 | Partial | Bearer auth exists with a single configured merchant. |
| NFR-4 | Partial | Merchant IDs scope local queries; token-to-merchant directory is pending. |
| NFR-5 | Missing | No public HTTPS deployment has been verified. |
| NFR-6 | Partial | `.env.example` exists; secret scanning and hosted secret setup are pending. |
| NFR-7 | Missing | Structured request/tool logging is not complete. |
| NFR-8 | Partial | Docker local setup exists; Postgres compose validation is pending. |
| NFR-9 | Done | Current local suite completes quickly. |
| NFR-10 | Partial | English is available; Portuguese dictionary/localization is pending. |
