from __future__ import annotations

import json
import hashlib
import unicodedata
from collections import defaultdict
from datetime import date, datetime, time, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .db import Database
from .models import Entry


def to_minor(amount: int | float | str | Decimal, exponent: int = 2) -> int:
    value = Decimal(str(amount)).quantize(Decimal(1).scaleb(-exponent), rounding=ROUND_HALF_UP)
    return int(value * (10**exponent))


def normalize_customer(value: str) -> str:
    text = unicodedata.normalize("NFKD", value or "")
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return " ".join(text.casefold().split())


def _request_hash(payload: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()


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
               metadata: dict[str, Any] | None = None,
               reversed_entry_id: int | None = None, request_hash: str | None = None) -> Entry:
        if amount_minor < 0:
            raise ValueError("amount_minor must be non-negative")
        with self.db.transaction() as conn:
            existing = conn.execute(
                "SELECT * FROM ledger_entries WHERE merchant_id=? AND idempotency_key=?",
                (merchant_id, idempotency_key)).fetchone()
            if existing:
                if request_hash and existing["request_hash"] and existing["request_hash"] != request_hash:
                    raise ValueError("idempotency key already used for a different request")
                return self._row(existing)
            cur = conn.execute(
                """INSERT INTO ledger_entries
                (merchant_id,idempotency_key,entry_type,amount_minor,currency,description,party,
                 quantity,unit_price_minor,product,metadata_json,reversed_entry_id,request_hash)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (merchant_id, idempotency_key, entry_type, amount_minor, self.currency, description, party,
                 quantity, unit_price_minor, product, json.dumps(metadata or {}), reversed_entry_id, request_hash),
            )
            return self._row(conn.execute("SELECT * FROM ledger_entries WHERE id=?", (cur.lastrowid,)).fetchone())

    def sale(self, merchant_id: str, amount: int | float | str | None = None, *, idempotency_key: str,
             product: str | None = None, quantity: int = 1, party: str | None = None,
             description: str = "Sale", unit_price: int | float | str | None = None,
             amount_paid: int | float | str | None = None, customer: str | None = None) -> Entry:
        if quantity < 1:
            raise ValueError("quantity must be at least 1")
        if unit_price is not None:
            total_minor = to_minor(unit_price) * quantity
            unit_minor = to_minor(unit_price)
        elif amount is not None:
            total_minor = to_minor(amount)
            unit_minor = total_minor // quantity
        else:
            raise ValueError("amount or unit_price is required")
        party = customer or party
        paid_minor = total_minor if amount_paid is None else to_minor(amount_paid)
        if paid_minor < 0 or paid_minor > total_minor:
            raise ValueError("amount_paid must be between zero and total")
        metadata = {"amount_paid_minor": paid_minor, "credit_minor": total_minor - paid_minor}
        request_hash = _request_hash({
            "type": "sale", "total": total_minor, "unit": unit_minor,
            "quantity": quantity, "product": product, "party": normalize_customer(party or ""),
            "paid": paid_minor,
        }) if unit_price is not None or amount_paid is not None else None
        entry = self.append(merchant_id, entry_type="sale", amount_minor=total_minor,
                           idempotency_key=idempotency_key, product=product, quantity=quantity,
                           unit_price_minor=unit_minor, party=party, description=description,
                           metadata=metadata, request_hash=request_hash)
        return entry

    def expense(self, merchant_id: str, amount: int | float | str, *, idempotency_key: str,
                category: str = "expense", description: str = "Expense") -> Entry:
        return self.append(merchant_id, entry_type="expense", amount_minor=to_minor(amount),
                           idempotency_key=idempotency_key, product=category, description=description)

    def credit(self, merchant_id: str, amount: int | float | str, *, idempotency_key: str,
               party: str, description: str = "Credit") -> Entry:
        return self.append(merchant_id, entry_type="credit", amount_minor=to_minor(amount),
                           idempotency_key=idempotency_key, party=party.strip(), description=description,
                           request_hash=_request_hash({"type": "credit", "amount": to_minor(amount),
                                                       "party": normalize_customer(party)}))

    def payment(self, merchant_id: str, amount: int | float | str, *, idempotency_key: str,
                party: str, description: str = "Payment received") -> Entry:
        key = normalize_customer(party)
        owed = self.credit_balances(merchant_id).get(key, 0)
        amount_minor = to_minor(amount)
        if amount_minor > owed:
            raise ValueError(f"payment exceeds balance for {party}")
        return self.append(merchant_id, entry_type="payment", amount_minor=amount_minor,
                           idempotency_key=idempotency_key, party=party.strip(), description=description,
                           request_hash=_request_hash({"type": "payment", "amount": amount_minor, "party": key}))

    def credit_balances(self, merchant_id: str) -> dict[str, int]:
        balances: dict[str, int] = {}
        for entry in reversed(self.list_entries(merchant_id, limit=10000)):
            if not entry.party:
                continue
            if entry.entry_type == "sale":
                delta = int((entry.metadata or {}).get("credit_minor", 0))
            elif entry.entry_type == "credit":
                delta = entry.amount_minor
            elif entry.entry_type == "payment":
                delta = -entry.amount_minor
            elif entry.entry_type == "undo":
                delta = -int((entry.metadata or {}).get("credit_minor", 0))
            else:
                continue
            key = normalize_customer(entry.party)
            balances[key] = max(0, balances.get(key, 0) + delta)
        return balances

    def undo_last(self, merchant_id: str, *, idempotency_key: str) -> Entry:
        for entry in self.list_entries(merchant_id, limit=10000):
            if entry.entry_type != "undo" and entry.reversed_entry_id is None:
                return self.undo(merchant_id, entry.id, idempotency_key=idempotency_key)
        raise KeyError("no live entries to undo")

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
        original_metadata = json.loads(target["metadata_json"])
        return self.append(merchant_id, entry_type="undo", amount_minor=target["amount_minor"],
                           idempotency_key=idempotency_key, description=f"Undo entry {entry_id}",
                           party=target["party"], product=target["product"],
                           quantity=target["quantity"], unit_price_minor=target["unit_price_minor"],
                           metadata={"original_entry_id": entry_id,
                                     "credit_minor": original_metadata.get("credit_minor", 0),
                                     "original_entry_type": target["entry_type"]},
                           reversed_entry_id=entry_id)

    def list_entries(self, merchant_id: str, limit: int = 100) -> list[Entry]:
        with self.db.transaction() as conn:
            rows = conn.execute("SELECT * FROM ledger_entries WHERE merchant_id=? ORDER BY id DESC LIMIT ?",
                                (merchant_id, limit)).fetchall()
        return [self._row(row) for row in rows]

    def _bounds(self, day: str | date | None, timezone_name: str) -> tuple[str | None, str | None]:
        if day is None:
            return None, None
        local_day = date.fromisoformat(day) if isinstance(day, str) else day
        if timezone_name.upper() in ("UTC", "Z"):
            tz = timezone.utc
        else:
            try:
                tz = ZoneInfo(timezone_name)
            except ZoneInfoNotFoundError as exc:
                raise ValueError(f"unknown timezone: {timezone_name}") from exc
        start = datetime.combine(local_day, time.min, tzinfo=tz).astimezone(timezone.utc)
        end = datetime.combine(local_day, time.max, tzinfo=tz).astimezone(timezone.utc)
        return start.strftime("%Y-%m-%d %H:%M:%S"), end.strftime("%Y-%m-%d %H:%M:%S")

    def summary(self, merchant_id: str, *, day: str | date | None = None,
                timezone_name: str = "UTC") -> dict[str, Any]:
        start, end = self._bounds(day, timezone_name)
        with self.db.transaction() as conn:
            sql = "SELECT entry_type, amount_minor FROM ledger_entries WHERE merchant_id=?"
            params: list[Any] = [merchant_id]
            if start:
                sql += " AND created_at BETWEEN ? AND ?"
                params += [start, end]
            rows = conn.execute(sql, params).fetchall()
        totals = defaultdict(int)
        for row in rows:
            sign = -1 if row["entry_type"] in ("expense", "credit", "undo") else 1
            totals[row["entry_type"]] += row["amount_minor"]
            totals["net"] += sign * row["amount_minor"]
        return dict(totals)

    def set_stock(self, merchant_id: str, product: str, quantity: int,
                  low_stock_threshold: int = 0) -> dict[str, Any]:
        if quantity < 0 or low_stock_threshold < 0:
            raise ValueError("stock values must be non-negative")
        product = " ".join(product.split()).strip()
        with self.db.transaction() as conn:
            conn.execute("""INSERT INTO stock_levels(merchant_id,product,quantity,low_stock_threshold)
                VALUES(?,?,?,?) ON CONFLICT(merchant_id,product) DO UPDATE SET
                quantity=excluded.quantity, low_stock_threshold=excluded.low_stock_threshold""",
                         (merchant_id, product, quantity, low_stock_threshold))
        return {"product": product, "quantity": quantity, "low_stock_threshold": low_stock_threshold}

    def stock(self, merchant_id: str, *, low_stock: bool = False) -> list[dict[str, Any]]:
        with self.db.transaction() as conn:
            rows = conn.execute(
                """SELECT s.product, s.quantity, s.low_stock_threshold,
                COALESCE(SUM(CASE WHEN e.entry_type='sale' THEN e.quantity
                    WHEN e.entry_type='undo' THEN -e.quantity ELSE 0 END), 0) sold
                FROM stock_levels s LEFT JOIN ledger_entries e
                ON e.merchant_id=s.merchant_id AND e.product=s.product
                WHERE s.merchant_id=? GROUP BY s.product, s.quantity, s.low_stock_threshold
                UNION ALL SELECT e.product, NULL, NULL,
                SUM(CASE WHEN e.entry_type='sale' THEN e.quantity WHEN e.entry_type='undo' THEN -e.quantity ELSE 0 END)
                FROM ledger_entries e WHERE e.merchant_id=? AND e.product IS NOT NULL
                AND NOT EXISTS (SELECT 1 FROM stock_levels s WHERE s.merchant_id=e.merchant_id AND s.product=e.product)
                GROUP BY e.product""",
                (merchant_id, merchant_id)).fetchall()
        result = [{"product": r["product"],
                   "quantity": (r["quantity"] - r["sold"]) if r["quantity"] is not None else None,
                   "low_stock_threshold": r["low_stock_threshold"], "sold": r["sold"]} for r in rows]
        return [x for x in result if not low_stock or (x["quantity"] is not None and x["quantity"] <= x["low_stock_threshold"])]

    def top_sellers(self, merchant_id: str, limit: int = 5, *, day: str | date | None = None,
                    timezone_name: str = "UTC") -> list[dict[str, Any]]:
        start, end = self._bounds(day, timezone_name)
        with self.db.transaction() as conn:
            sql = """SELECT product, SUM(CASE WHEN entry_type='sale' THEN quantity
                     WHEN entry_type='undo' THEN -quantity ELSE 0 END) sold
                     FROM ledger_entries WHERE merchant_id=? AND product IS NOT NULL"""
            params: list[Any] = [merchant_id]
            if start:
                sql += " AND created_at BETWEEN ? AND ?"
                params += [start, end]
            sql += " GROUP BY product ORDER BY sold DESC LIMIT ?"
            params.append(limit)
            rows = conn.execute(sql, params).fetchall()
        return [{"product": r["product"], "sold": r["sold"]} for r in rows]
