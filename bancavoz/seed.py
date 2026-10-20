from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta

from .db import Database
from .service import LedgerService


def main() -> None:
    service = LedgerService(Database(os.getenv("BANCAVOZ_DATABASE_URL", "sqlite:///./bancavoz.db")))
    now = datetime.now(UTC)
    for offset in range(7, 0, -1):
        sale = service.sale("demo", unit_price=60 + offset, idempotency_key=f"seed-sale-{offset}",
                            product="chai" if offset % 2 else "rice", quantity=offset)
        expense = service.expense("demo", 50 + offset, idempotency_key=f"seed-expense-{offset}",
                                  category="supplies")
        day = (now - timedelta(days=offset)).strftime("%Y-%m-%d %H:%M:%S")
        with service.db.transaction() as conn:
            conn.execute("UPDATE ledger_entries SET created_at=? WHERE id IN (?, ?)", (day, sale.id, expense.id))
    sale = service.sale("demo", unit_price=100, amount_paid=50, customer="Maria",
                        idempotency_key="seed-maria-credit", product="rice", quantity=1)
    with service.db.transaction() as conn:
        conn.execute("UPDATE ledger_entries SET created_at=? WHERE id=?",
                     ((now - timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S"), sale.id))
    print(service.summary("demo"))


if __name__ == "__main__":
    main()
