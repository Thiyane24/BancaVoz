# Test plan and traceability

## How to run

```powershell
python -m pytest -q
python -m pytest --cov=bancavoz --cov-report=term-missing -q
python -m ruff check bancavoz tests
python -m mypy bancavoz
python -m compileall -q bancavoz
python scripts/generate_mcp_tools_doc.py
```

The measured local coverage run on 2026-10-20 reported **70% total coverage
(590 statements, 177 missed)**. Coverage is not a release gate in CI yet.

## Traceability

| Requirement | Test or smoke command | Status |
| --- | --- | --- |
| Health endpoint | `tests/test_api.py::test_healthz` | Pass |
| Static web pages | `tests/test_api.py::test_static_pages_and_assets` | Pass |
| Bearer authentication | `tests/test_api.py::test_bearer_auth` | Pass |
| Security headers and readiness | `tests/test_api.py::test_security_headers_and_readyz` | Pass |
| Decimal HTTP inputs | `tests/test_api.py::test_http_generates_empty_idempotency_key` | Pass |
| Idempotency and conflicts | `tests/test_service.py::test_empty_idempotency_key_is_generated_and_conflicts_are_rejected` | Pass |
| Undo selection | `tests/test_service.py::test_undo_last_skips_already_reversed_entries` | Pass |
| Credit reversal | `tests/test_service.py::test_undo_balance_deltas_restore_payment_and_remove_credit` | Pass |
| Summary totals | `tests/test_service.py::test_summary_returns_live_business_totals_only` | Pass |
| Strict sale validation | `tests/test_service.py::test_sale_requires_unit_price_customer_for_partial_and_rejects_zero` | Pass |
| Digest fact shape | `tests/test_digest.py::test_digest_uses_live_summary_fields_and_previous_week_facts` | Pass |
| Stock baseline reset | `tests/test_service.py::test_idempotency_conflict_and_stock_low_stock` | Pass |
| Concise speech | `tests/test_speech.py::test_sale_speech_contains_real_numbers_and_stays_short` | Pass |
| Official MCP initialize/tools-list | `tests/test_api.py::test_official_mcp_tools_list` | Pass |
| Public HTTPS / Postgres | No test or smoke run exists | Not verified |
| Bedrock Converse/numeric gate/cache | No passing test exists | Not verified |
| Rate limiting / merchant token directory | No passing test exists | Not verified |
