from bancavoz.db import Database
from bancavoz.service import LedgerService, to_minor


def service():
    return LedgerService(Database("sqlite:///:memory:"))


def test_minor_units_and_idempotency():
    ledger = service()
    assert to_minor("12.34") == 1234
    first = ledger.sale("m1", unit_price="12.34", idempotency_key="a", product="tea")
    second = ledger.sale("m1", unit_price="12.34", idempotency_key="a", product="tea")
    assert first.id == second.id
    assert ledger.summary("m1")["sales"] == 1234


def test_merchant_scope_and_undo():
    ledger = service()
    entry = ledger.sale("a", unit_price=10, idempotency_key="a1", product="x")
    ledger.sale("b", unit_price=20, idempotency_key="a1", product="x")
    assert len(ledger.list_entries("a")) == 1
    undone = ledger.undo("a", entry.id, idempotency_key="undo-a1")
    assert undone.entry_type == "undo"
    assert ledger.summary("a")["profit"] == 0


def test_top_sellers():
    ledger = service()
    ledger.sale("m", unit_price=10, idempotency_key="1", product="chai", quantity=2)
    ledger.sale("m", unit_price=10, idempotency_key="2", product="samosa", quantity=3)
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


def test_sale_requires_unit_price_customer_for_partial_and_rejects_zero():
    ledger = service()
    for kwargs in (
        {"amount": "10"},
        {"unit_price": "0"},
        {"unit_price": "10", "amount_paid": "5"},
    ):
        try:
            ledger.sale("m", idempotency_key=f"invalid-{len(kwargs)}", **kwargs)
        except ValueError:
            pass
        else:
            raise AssertionError("expected strict sale validation")


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
    ledger.set_stock("m", "rice", 3, low_stock_threshold=3)
    assert ledger.stock("m")[0]["quantity"] == 3
    assert ledger.stock("m", low_stock=True)[0]["product"] == "rice"
    ledger.set_stock("m", "rice", 10, low_stock_threshold=2)
    assert ledger.stock("m")[0]["quantity"] == 10


def test_period_top_sellers():
    ledger = service()
    ledger.sale("m", unit_price=10, idempotency_key="today", product="rice", quantity=2)
    with ledger.db.transaction() as conn:
        conn.execute("UPDATE ledger_entries SET created_at='2020-01-01 00:00:00' WHERE id=1")
    ledger.sale("m", unit_price=20, idempotency_key="current", product="oil", quantity=1)
    assert ledger.top_sellers("m", day="2099-01-01") == []
    assert ledger.top_sellers("m")[0]["product"] == "oil"


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


def test_undo_balance_deltas_restore_payment_and_remove_credit():
    ledger = service()
    sale = ledger.sale("m", unit_price="10", quantity=1, amount_paid="0",
                       customer="Maria", product="rice", idempotency_key="sale-credit")
    payment = ledger.payment("m", "4", party="Maria", idempotency_key="payment")
    assert ledger.credit_balances("m")["maria"] == 600
    ledger.undo("m", payment.id, idempotency_key="undo-payment")
    assert ledger.credit_balances("m")["maria"] == 1000
    ledger.undo("m", sale.id, idempotency_key="undo-sale")
    assert ledger.credit_balances("m")["maria"] == 0


def test_summary_returns_live_business_totals_only():
    ledger = service()
    ledger.sale("m", unit_price="10", quantity=2, amount_paid="15",
                customer="Maria", product="rice", idempotency_key="summary-sale")
    ledger.expense("m", "3", idempotency_key="summary-expense", category="transport")
    payment = ledger.payment("m", "2", party="Maria", idempotency_key="summary-payment")
    ledger.undo("m", payment.id, idempotency_key="summary-undo")
    summary = ledger.summary("m")
    assert summary == {
        "sales": 2000,
        "expenses": 300,
        "profit": 1700,
        "credit_given": 500,
        "credit_collected": 0,
        "entry_count": 2,
    }
