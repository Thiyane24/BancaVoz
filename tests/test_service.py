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


def test_sale_unit_price_partial_credit_and_customer_normalization():
    ledger = service()
    entry = ledger.sale("m", unit_price="10.00", quantity=3, amount_paid="12",
                        idempotency_key="partial", product="rice", customer="  MÁRIA   José ")
    assert entry.amount_minor == 3000
    assert entry.unit_price_minor == 1000
    assert ledger.credit_balances("m")["maria jose"] == 1800
    ledger.payment("m", "18", idempotency_key="payment", party="maria jose")
    assert ledger.credit_balances("m")["maria jose"] == 0


def test_idempotency_conflict_and_stock_low_stock():
    ledger = service()
    ledger.sale("m", unit_price=10, quantity=2, amount_paid=20,
                idempotency_key="strict", product="rice")
    try:
        ledger.sale("m", unit_price=11, quantity=2, amount_paid=22,
                    idempotency_key="strict", product="rice")
    except ValueError as exc:
        assert "different request" in str(exc)
    else:
        raise AssertionError("expected idempotency conflict")
    ledger.set_stock("m", "rice", 3, low_stock_threshold=2)
    assert ledger.stock("m")[0]["quantity"] == 1
    assert ledger.stock("m", low_stock=True)[0]["product"] == "rice"


def test_period_top_sellers():
    ledger = service()
    ledger.sale("m", 10, idempotency_key="today", product="rice", quantity=2)
    assert ledger.top_sellers("m", day="2099-01-01") == []


def test_empty_idempotency_key_is_generated_and_conflicts_are_rejected():
    ledger = service()
    first = ledger.expense("m", "10", idempotency_key="")
    assert first.idempotency_key
    try:
        ledger.expense("m", "11", idempotency_key=first.idempotency_key)
    except ValueError as exc:
        assert "different request" in str(exc)
    else:
        raise AssertionError("expected idempotency conflict")


def test_undo_last_skips_already_reversed_entries():
    ledger = service()
    first = ledger.expense("m", "10", idempotency_key="first")
    second = ledger.expense("m", "20", idempotency_key="second")
    undo_second = ledger.undo_last("m", idempotency_key="")
    undo_first = ledger.undo_last("m", idempotency_key="")
    assert undo_second.reversed_entry_id == second.id
    assert undo_first.reversed_entry_id == first.id
    assert undo_second.id != undo_first.id
