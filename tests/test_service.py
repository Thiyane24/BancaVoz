from bancavoz.db import Database
from bancavoz.service import LedgerService, to_minor


def service():
    return LedgerService(Database("sqlite:///:memory:"))


def test_minor_units_and_idempotency():
    ledger = service()
    assert to_minor("12.34") == 1234
    first = ledger.sale("m1", "12.34", idempotency_key="a", product="tea")
    second = ledger.sale("m1", "99", idempotency_key="a", product="wrong")
    assert first.id == second.id
    assert ledger.summary("m1")["sale"] == 1234


def test_merchant_scope_and_undo():
    ledger = service()
    entry = ledger.sale("a", 10, idempotency_key="a1", product="x")
    ledger.sale("b", 20, idempotency_key="a1", product="x")
    assert len(ledger.list_entries("a")) == 1
    undone = ledger.undo("a", entry.id, idempotency_key="undo-a1")
    assert undone.entry_type == "undo"
    assert ledger.summary("a")["net"] == 0


def test_top_sellers():
    ledger = service()
    ledger.sale("m", 10, idempotency_key="1", product="chai", quantity=2)
    ledger.sale("m", 10, idempotency_key="2", product="samosa", quantity=3)
    assert ledger.top_sellers("m")[0]["product"] == "samosa"
