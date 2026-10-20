from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Entry:
    id: int
    merchant_id: str
    idempotency_key: str
    entry_type: str
    amount_minor: int
    currency: str
    description: str
    party: str | None = None
    quantity: int = 0
    unit_price_minor: int | None = None
    product: str | None = None
    metadata: dict[str, Any] | None = None
    reversed_entry_id: int | None = None
    created_at: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {k: v for k, v in self.__dict__.items() if k != "metadata"} | {"metadata": self.metadata or {}}
