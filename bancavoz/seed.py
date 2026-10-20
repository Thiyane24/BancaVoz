from __future__ import annotations

import os

from .db import Database
from .service import LedgerService


def main() -> None:
    service = LedgerService(Database(os.getenv("BANCAVOZ_DATABASE_URL", "sqlite:///./bancavoz.db")))
    service.sale("demo", 120, idempotency_key="seed-sale-1", product="chai", quantity=2)
    service.expense("demo", 50, idempotency_key="seed-expense-1", category="supplies")
    print(service.summary("demo"))


if __name__ == "__main__":
    main()
