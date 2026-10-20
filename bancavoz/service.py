from __future__ import annotations

import json
from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from .db import Database
from .models import Entry


def to_minor(amount: int | float | str | Decimal, exponent: int = 2) -> int:
    value = Decimal(str(amount)).quantize(Decimal(1).scaleb(-exponent), rounding=ROUND_HALF_UP)
    return int(value * (10**exponent))


class LedgerService:
    def __init__(self, db: Database, currency: str = "MZN"):
        self.db, self.currency = db, currency

    def _row(self, row: Any) -> Entry:
        return Entry(
            id=row["id"], merchant_id=row["merchant_id"], idempotency_key=row["idempotency_key"],
            entry_type=row["entry_type"], amount_minor=row["amount_minor"], currency=row["currency"],
            description=row["description"], party=row["party"], quantity=row["quantity"],
            unit_price_minor=row["unit_price_minor"], product=row["product"],
            metadata=json.loads(row["metadata_json"]), reversed_entry_id=row["reversed_entry_id"],
            created_at=row["created_at"],
        )

    def append(self, merchant_id: str, *, entry_type: str, amount_minor: int, idempotency_key: str,
               description: str = "", party: str | None = None, quantity: int = 0,
               unit_price_minor: int | None = None, product: str | None = None,
               metadata: dict[str, Any] | None = None) -> Entry:
        if amount_minor < 0:
            raise ValueError("amount_minor must be non-negative")
        with self.db.transaction() as conn:
            existing = conn.execute(
                "SELECT * FROM ledger_entries WHERE merchant_id=? AND idempotency_key=?",
                (merchant_id, idempotency_key)).fetchone()
            if existing:
                return self._row(existing)
            cur = conn.execute(
                """INSERT INTO ledger_entries
                (merchant_id,idempotency_key,entry_type,amount_minor,currency,description,party,
                 quantity,unit_price_minor,product,metadata_json)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (merchant_id, idempotency_key, entry_type, amount_minor, self.currency, description, party,
                 quantity, unit_price_minor, product, json.dumps(metadata or {})),
            )
            return self._row(conn.execute("SELECT * FROM ledger_entries WHERE id=?", (cur.lastrowid,)).fetchone())

    def sale(self, merchant_id: str, amount: int | float | str, *, idempotency_key: str,
             product: str | None = None, quantity: int = 1, party: str | None = None,
             description: str = "Sale") -> Entry:
        return self.append(merchant_id, entry_type="sale", amount_minor=to_minor(amount),
                           idempotency_key=idempotency_key, product=product, quantity=quantity,
                           unit_price_minor=to_minor(amount) // quantity if quantity else None,
                           party=party, description=description)

    def expense(self, merchant_id: str, amount: int | float | str, *, idempotency_key: str,
                category: str = "expense", description: str = "Expense") -> Entry:
        return self.append(merchant_id, entry_type="expense", amount_minor=to_minor(amount),
                           idempotency_key=idempotency_key, product=category, description=description)

    def credit(self, merchant_id: str, amount: int | float | str, *, idempotency_key: str,
               party: str, description: str = "Credit") -> Entry:
        return self.append(merchant_id, entry_type="credit", amount_minor=to_minor(amount),
                           idempotency_key=idempotency_key, party=party, description=description)

    def payment(self, merchant_id: str, amount: int | float | str, *, idempotency_key: str,
                party: str, description: str = "Payment received") -> Entry:
        return self.append(merchant_id, entry_type="payment", amount_minor=to_minor(amount),
                           idempotency_key=idempotency_key, party=party, description=description)

    def undo(self, merchant_id: str, entry_id: int, *, idempotency_key: str) -> Entry:
        with self.db.transaction() as conn:
            target = conn.execute("SELECT * FROM ledger_entries WHERE id=? AND merchant_id=?",
                                  (entry_id, merchant_id)).fetchone()
            if not target:
                raise KeyError("entry not found")
            if target["reversed_entry_id"]:
                raise ValueError("entry is already an undo")
            undone = conn.execute("SELECT * FROM ledger_entries WHERE reversed_entry_id=? AND merchant_id=?",
                                  (entry_id, merchant_id)).fetchone()
            if undone:
                return self._row(undone)
        return self.append(merchant_id, entry_type="undo", amount_minor=target["amount_minor"],
                           idempotency_key=idempotency_key, description=f"Undo entry {entry_id}",
                           party=target["party"], product=target["product"],
                           metadata={"original_entry_id": entry_id})

    def list_entries(self, merchant_id: str, limit: int = 100) -> list[Entry]:
        with self.db.transaction() as conn:
            rows = conn.execute("SELECT * FROM ledger_entries WHERE merchant_id=? ORDER BY id DESC LIMIT ?",
                                (merchant_id, limit)).fetchall()
        return [self._row(row) for row in rows]

    def summary(self, merchant_id: str) -> dict[str, Any]:
        with self.db.transaction() as conn:
            rows = conn.execute("SELECT entry_type, amount_minor FROM ledger_entries WHERE merchant_id=?",
                                (merchant_id,)).fetchall()
        totals = defaultdict(int)
        for row in rows:
            sign = -1 if row["entry_type"] in ("expense", "credit", "undo") else 1
            totals[row["entry_type"]] += row["amount_minor"]
            totals["net"] += sign * row["amount_minor"]
        return dict(totals)

    def stock(self, merchant_id: str) -> list[dict[str, Any]]:
        with self.db.transaction() as conn:
            rows = conn.execute(
                "SELECT product, SUM(CASE WHEN entry_type='sale' THEN quantity "
                "WHEN entry_type='undo' THEN -quantity ELSE 0 END) sold "
                "FROM ledger_entries WHERE merchant_id=? AND product IS NOT NULL GROUP BY product",
                (merchant_id,)).fetchall()
        return [{"product": r["product"], "sold": r["sold"]} for r in rows]

    def top_sellers(self, merchant_id: str, limit: int = 5) -> list[dict[str, Any]]:
        return sorted(self.stock(merchant_id), key=lambda x: x["sold"], reverse=True)[:limit]
