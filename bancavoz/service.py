from __future__ import annotations

import hashlib
import json
import unicodedata
from datetime import UTC, date, datetime, time, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Any
from uuid import uuid4
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .db import Database
from .models import Entry


def to_minor(amount: float | str | Decimal, exponent: int = 2) -> int:
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
        idempotency_key = idempotency_key or str(uuid4())
        metadata = dict(metadata or {})
        metadata.setdefault("credit_delta", 0)
        request_hash = request_hash or _request_hash({
            "entry_type": entry_type,
            "amount_minor": amount_minor,
            "description": description,
            "party": normalize_customer(party or ""),
            "quantity": quantity,
            "unit_price_minor": unit_price_minor,
            "product": " ".join((product or "").split()).casefold(),
            "metadata": metadata,
            "reversed_entry_id": reversed_entry_id,
        })
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
                 quantity, unit_price_minor, product, json.dumps(metadata), reversed_entry_id, request_hash),
            )
            return self._row(conn.execute("SELECT * FROM ledger_entries WHERE id=?", (cur.lastrowid,)).fetchone())

    def sale(self, merchant_id: str, amount: float | str | Decimal | None = None, *, idempotency_key: str,
             product: str | None = None, quantity: int = 1, party: str | None = None,
             description: str = "Sale", unit_price: float | str | Decimal | None = None,
             amount_paid: float | str | Decimal | None = None, customer: str | None = None) -> Entry:
        if quantity < 1:
            raise ValueError("quantity must be at least 1")
        if unit_price is None:
            raise ValueError("unit_price is required")
        unit_minor = to_minor(unit_price)
        if unit_minor <= 0:
            raise ValueError("unit_price must be greater than zero")
        if amount is not None:
            raise ValueError("amount-only sales are not supported; provide unit_price")
        total_minor = unit_minor * quantity
        party = customer or party
        paid_minor = total_minor if amount_paid is None else to_minor(amount_paid)
        if paid_minor < 0 or paid_minor > total_minor:
            raise ValueError("amount_paid must be between zero and total")
        if paid_minor < total_minor and not party:
            raise ValueError("customer is required when amount_paid is less than total")
        product = " ".join((product or "").split())
        if not product:
            raise ValueError("item is required")
        metadata = {
            "amount_paid_minor": paid_minor,
            "credit_minor": total_minor - paid_minor,
            "credit_delta": total_minor - paid_minor,
        }
        request_hash = _request_hash({
            "type": "sale", "total": total_minor, "unit": unit_minor,
            "quantity": quantity, "product": product, "party": normalize_customer(party or ""),
            "paid": paid_minor,
        })
        entry = self.append(merchant_id, entry_type="sale", amount_minor=total_minor,
                           idempotency_key=idempotency_key, product=product, quantity=quantity,
                           unit_price_minor=unit_minor, party=party, description=description,
                           metadata=metadata, request_hash=request_hash)
        return entry

    def expense(self, merchant_id: str, amount: float | str | Decimal, *, idempotency_key: str,
                category: str = "expense", description: str = "Expense") -> Entry:
        return self.append(merchant_id, entry_type="expense", amount_minor=to_minor(amount),
                           idempotency_key=idempotency_key, product=category, description=description)

    def credit(self, merchant_id: str, amount: float | str | Decimal, *, idempotency_key: str,
               party: str, description: str = "Credit") -> Entry:
        return self.append(merchant_id, entry_type="credit", amount_minor=to_minor(amount),
                           idempotency_key=idempotency_key, party=party.strip(), description=description,
                           metadata={"credit_delta": to_minor(amount)},
                           request_hash=_request_hash({"type": "credit", "amount": to_minor(amount),
                                                       "party": normalize_customer(party)}))

    def payment(self, merchant_id: str, amount: float | str | Decimal, *, idempotency_key: str,
                party: str, description: str = "Payment received") -> Entry:
        key = normalize_customer(party)
        owed = self.credit_balances(merchant_id).get(key, 0)
        amount_minor = to_minor(amount)
        if amount_minor > owed:
            raise ValueError(f"payment exceeds balance for {party}")
        return self.append(merchant_id, entry_type="payment", amount_minor=amount_minor,
                           idempotency_key=idempotency_key, party=party.strip(), description=description,
                           metadata={"credit_delta": -amount_minor},
                           request_hash=_request_hash({"type": "payment", "amount": amount_minor, "party": key}))

    def credit_balances(self, merchant_id: str) -> dict[str, int]:
        balances: dict[str, int] = {}
        for entry in reversed(self.list_entries(merchant_id, limit=10000)):
            if not entry.party:
                continue
            delta = int((entry.metadata or {}).get("credit_delta", 0))
            key = normalize_customer(entry.party)
            balances[key] = balances.get(key, 0) + delta
        return balances

    def undo_last(self, merchant_id: str, *, idempotency_key: str) -> Entry:
        with self.db.transaction() as conn:
            row = conn.execute(
                """SELECT e.* FROM ledger_entries e
                WHERE e.merchant_id=? AND e.entry_type <> 'undo'
                  AND NOT EXISTS (
                    SELECT 1 FROM ledger_entries u
                    WHERE u.merchant_id=e.merchant_id
                      AND u.entry_type='undo'
                      AND u.reversed_entry_id=e.id
                  )
                ORDER BY e.id DESC LIMIT 1""",
                (merchant_id,),
            ).fetchone()
        if row:
            return self.undo(merchant_id, row["id"], idempotency_key=idempotency_key)
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
                                     "credit_delta": -int(original_metadata.get("credit_delta", 0)),
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
            tz: Any = UTC
        else:
            try:
                tz = ZoneInfo(timezone_name)
            except ZoneInfoNotFoundError as exc:
                raise ValueError(f"unknown timezone: {timezone_name}") from exc
        start = datetime.combine(local_day, time.min, tzinfo=tz).astimezone(UTC)
        end = datetime.combine(local_day, time.max, tzinfo=tz).astimezone(UTC)
        return start.strftime("%Y-%m-%d %H:%M:%S"), end.strftime("%Y-%m-%d %H:%M:%S")

    def summary(self, merchant_id: str, *, day: str | date | None = None,
                timezone_name: str = "Africa/Maputo") -> dict[str, Any]:
        if day is None:
            day = datetime.now(UTC if timezone_name.upper() in ("UTC", "Z") else ZoneInfo(timezone_name)).date()
        start, end = self._bounds(day, timezone_name)
        with self.db.transaction() as conn:
            sql = """SELECT e.entry_type, e.amount_minor, e.metadata_json
                     FROM ledger_entries e
                     WHERE e.merchant_id=? AND e.entry_type <> 'undo'
                       AND NOT EXISTS (
                         SELECT 1 FROM ledger_entries u
                         WHERE u.merchant_id=e.merchant_id
                           AND u.entry_type='undo'
                           AND u.reversed_entry_id=e.id
                       )"""
            params: list[Any] = [merchant_id]
            if start:
                sql += " AND created_at BETWEEN ? AND ?"
                params += [start, end]
            rows = conn.execute(sql, params).fetchall()
        totals = {
            "sales": 0,
            "expenses": 0,
            "profit": 0,
            "credit_given": 0,
            "credit_collected": 0,
            "entry_count": 0,
        }
        for row in rows:
            metadata = json.loads(row["metadata_json"])
            if row["entry_type"] == "sale":
                totals["sales"] += row["amount_minor"]
                totals["credit_given"] += int(metadata.get("credit_delta", 0))
            elif row["entry_type"] == "expense":
                totals["expenses"] += row["amount_minor"]
            elif row["entry_type"] == "credit":
                totals["credit_given"] += int(metadata.get("credit_delta", 0))
            elif row["entry_type"] == "payment":
                totals["credit_collected"] += row["amount_minor"]
            totals["entry_count"] += 1
        totals["profit"] = totals["sales"] - totals["expenses"]
        return totals

    def set_stock(self, merchant_id: str, product: str, quantity: int,
                  low_stock_threshold: int = 0) -> dict[str, Any]:
        if quantity < 0 or low_stock_threshold < 0:
            raise ValueError("stock values must be non-negative")
        product = " ".join(product.split()).strip()
        with self.db.transaction() as conn:
            sold = conn.execute(
                """SELECT COALESCE(SUM(CASE WHEN entry_type='sale' THEN quantity
                    WHEN entry_type='undo' THEN -quantity ELSE 0 END), 0)
                   FROM ledger_entries WHERE merchant_id=? AND product=?""",
                (merchant_id, product),
            ).fetchone()[0]
            conn.execute("""INSERT INTO stock_levels(merchant_id,product,quantity,low_stock_threshold,sold_baseline)
                VALUES(?,?,?,?,?) ON CONFLICT(merchant_id,product) DO UPDATE SET
                quantity=excluded.quantity, low_stock_threshold=excluded.low_stock_threshold,
                sold_baseline=excluded.sold_baseline""",
                         (merchant_id, product, quantity, low_stock_threshold, sold))
        return {"product": product, "quantity": quantity, "low_stock_threshold": low_stock_threshold}

    def stock(self, merchant_id: str, *, low_stock: bool = False) -> list[dict[str, Any]]:
        with self.db.transaction() as conn:
            rows = conn.execute(
                """SELECT s.product, s.quantity, s.low_stock_threshold,
                COALESCE(SUM(CASE WHEN e.entry_type='sale' THEN e.quantity
                    WHEN e.entry_type='undo' THEN -e.quantity ELSE 0 END), 0) - s.sold_baseline sold
                FROM stock_levels s LEFT JOIN ledger_entries e
                ON e.merchant_id=s.merchant_id AND e.product=s.product
                WHERE s.merchant_id=? GROUP BY s.product, s.quantity, s.low_stock_threshold, s.sold_baseline
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
                    period: str = "today",
                    timezone_name: str = "UTC") -> list[dict[str, Any]]:
        if day is None:
            tz = UTC if timezone_name.upper() in ("UTC", "Z") else ZoneInfo(timezone_name)
            current = datetime.now(tz).date()
            day = current
        if period not in ("today", "week", "month"):
                raise ValueError("period must be today, week, or month")
        local_day = date.fromisoformat(day) if isinstance(day, str) else day
        range_start = local_day
        range_end = local_day
        if period == "week":
            range_start = local_day - timedelta(days=local_day.weekday())
            range_end = range_start + timedelta(days=6)
        elif period == "month":
            range_start = local_day.replace(day=1)
            next_month = (range_start.replace(day=28) + timedelta(days=4)).replace(day=1)
            range_end = next_month - timedelta(days=1)
        start, _ = self._bounds(range_start, timezone_name)
        _, end = self._bounds(range_end, timezone_name)
        with self.db.transaction() as conn:
            sql = """SELECT product, SUM(quantity) sold, SUM(amount_minor) revenue
                     FROM ledger_entries e WHERE merchant_id=? AND entry_type='sale'
                     AND product IS NOT NULL
                     AND NOT EXISTS (SELECT 1 FROM ledger_entries u
                       WHERE u.entry_type='undo' AND u.reversed_entry_id=e.id)"""
            params: list[Any] = [merchant_id]
            if start:
                sql += " AND created_at BETWEEN ? AND ?"
                params += [start, end]
            sql += " GROUP BY product ORDER BY revenue DESC LIMIT ?"
            params.append(limit)
            rows = conn.execute(sql, params).fetchall()
        return [{"product": r["product"], "sold": r["sold"], "revenue": r["revenue"]} for r in rows]
