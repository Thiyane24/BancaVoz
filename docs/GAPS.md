# Verified requirement gaps

This is the status source of truth. “Pass” means a named test or smoke command
passed. Unverified claims remain open.

| Area | Test / evidence | Status |
| --- | --- | --- |
| Local FastAPI health/static/auth | `pytest tests/test_api.py -q` | Pass |
| Idempotency UUIDs and conflicts | `pytest tests/test_service.py -q` | Pass |
| Undo and credit restoration | `pytest tests/test_service.py -q` | Pass |
| Summary totals and reversal exclusion | `test_summary_returns_live_business_totals_only` | Pass |
| Africa/Maputo timezone data | `pytest tests/test_service.py -q` with `tzdata` installed | Pass |
| Strict sale inputs | `test_sale_requires_unit_price_customer_for_partial_and_rejects_zero` | Pass |
| Digest summary-field compatibility | `pytest tests/test_digest.py -q` | Pass |
| Revenue-ranked sellers and stock reset | `pytest tests/test_service.py -q` | Pass |
| Numeric concise speech | `pytest tests/test_speech.py -q` | Pass |
| Official MCP initialize/tools-list | `test_official_mcp_tools_list` and doc-generation script | Pass |
| Full simulator six-utterance contract | No complete passing test | Open |
| Persistent digest cache/invalidation | No passing test | Open |
| Bedrock Converse and numeric rejection | No passing test | Open |
| PostgreSQL adapter, merchants, migrations | API/deployment tests pass; hosted smoke not run | Partial |
| Rate limiting and structured logs | API/deployment tests pass; multi-replica limiter not verified | Partial |
| Token-to-merchant hashed lookup | API/deployment tests pass; hosted rotation not run | Partial |
| Public HTTPS deployment | No public URL smoke run recorded | Open |
| Docker/Postgres CI validation | CI workflow now defines Postgres migration smoke | Partial |
