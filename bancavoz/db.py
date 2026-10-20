from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

SCHEMA = """
CREATE TABLE IF NOT EXISTS ledger_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    merchant_id TEXT NOT NULL,
    idempotency_key TEXT NOT NULL,
    entry_type TEXT NOT NULL,
    amount_minor INTEGER NOT NULL,
    currency TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    party TEXT,
    quantity INTEGER NOT NULL DEFAULT 0,
    unit_price_minor INTEGER,
    product TEXT,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    reversed_entry_id INTEGER,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (merchant_id, idempotency_key),
    FOREIGN KEY (reversed_entry_id) REFERENCES ledger_entries(id)
);
CREATE INDEX IF NOT EXISTS idx_entries_merchant_time
  ON ledger_entries (merchant_id, created_at);
CREATE INDEX IF NOT EXISTS idx_entries_merchant_product
  ON ledger_entries (merchant_id, product);
"""


class Database:
    """Tiny DB adapter. SQLite is used for tests/local; schema is portable to Postgres."""

    def __init__(self, url: str = "sqlite:///./bancavoz.db"):
        self.url = url
        if not url.startswith("sqlite:///"):
            raise ValueError("Postgres URLs require the optional psycopg adapter; use sqlite for the MVP")
        raw = url.removeprefix("sqlite:///")
        self.path = ":memory:" if raw in (":memory:", "") else str(Path(raw))
        self._conn: sqlite3.Connection | None = None

    def connect(self) -> None:
        if self._conn is None:
            self._conn = sqlite3.connect(self.path, check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA foreign_keys=ON")
            self._conn.executescript(SCHEMA)
            self._conn.commit()

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        self.connect()
        assert self._conn is not None
        try:
            yield self._conn
            self._conn.commit()
        except Exception:
            self._conn.rollback()
            raise

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None
