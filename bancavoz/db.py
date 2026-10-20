from __future__ import annotations

import hashlib
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from threading import Lock
from typing import Any

SQLITE_SCHEMA = """
CREATE TABLE IF NOT EXISTS merchants (
    id TEXT PRIMARY KEY,
    token_hash TEXT NOT NULL UNIQUE,
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
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
    category TEXT,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    reversed_entry_id INTEGER,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    request_hash TEXT,
    UNIQUE (merchant_id, idempotency_key),
    FOREIGN KEY (merchant_id) REFERENCES merchants(id),
    FOREIGN KEY (reversed_entry_id) REFERENCES ledger_entries(id)
);
CREATE INDEX IF NOT EXISTS idx_entries_merchant_time
  ON ledger_entries (merchant_id, created_at);
CREATE INDEX IF NOT EXISTS idx_entries_merchant_product
  ON ledger_entries (merchant_id, product);
CREATE TABLE IF NOT EXISTS stock_levels (
    merchant_id TEXT NOT NULL,
    product TEXT NOT NULL,
    quantity INTEGER NOT NULL CHECK (quantity >= 0),
    low_stock_threshold INTEGER NOT NULL DEFAULT 0,
    sold_baseline INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (merchant_id, product),
    FOREIGN KEY (merchant_id) REFERENCES merchants(id)
);
CREATE TABLE IF NOT EXISTS digests (
    merchant_id TEXT NOT NULL,
    digest_date TEXT NOT NULL,
    facts_json TEXT NOT NULL,
    narrative TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (merchant_id, digest_date),
    FOREIGN KEY (merchant_id) REFERENCES merchants(id)
);
"""

POSTGRES_SCHEMA = """
CREATE TABLE IF NOT EXISTS merchants (
    id TEXT PRIMARY KEY,
    token_hash TEXT NOT NULL UNIQUE,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS ledger_entries (
    id BIGSERIAL PRIMARY KEY,
    merchant_id TEXT NOT NULL REFERENCES merchants(id),
    idempotency_key TEXT NOT NULL,
    entry_type TEXT NOT NULL,
    amount_minor BIGINT NOT NULL,
    currency TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    party TEXT,
    quantity INTEGER NOT NULL DEFAULT 0,
    unit_price_minor BIGINT,
    product TEXT,
    category TEXT,
    metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    reversed_entry_id BIGINT REFERENCES ledger_entries(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    request_hash TEXT,
    UNIQUE (merchant_id, idempotency_key)
);
CREATE INDEX IF NOT EXISTS idx_entries_merchant_time ON ledger_entries (merchant_id, created_at);
CREATE INDEX IF NOT EXISTS idx_entries_merchant_product ON ledger_entries (merchant_id, product);
CREATE TABLE IF NOT EXISTS stock_levels (
    merchant_id TEXT NOT NULL REFERENCES merchants(id),
    product TEXT NOT NULL,
    quantity INTEGER NOT NULL CHECK (quantity >= 0),
    low_stock_threshold INTEGER NOT NULL DEFAULT 0,
    sold_baseline INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (merchant_id, product)
);
CREATE TABLE IF NOT EXISTS digests (
    merchant_id TEXT NOT NULL REFERENCES merchants(id),
    digest_date DATE NOT NULL,
    facts_json JSONB NOT NULL,
    narrative TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (merchant_id, digest_date)
);
"""


def _pg_sql(sql: str) -> str:
    return sql.replace("?", "%s")


class ConnectionAdapter:
    def __init__(self, connection: Any, postgres: bool):
        self.connection = connection
        self.postgres = postgres

    def execute(self, sql: str, params: Any = ()):
        return self.connection.execute(_pg_sql(sql) if self.postgres else sql, params)


class Database:
    """SQLite test adapter and PostgreSQL production adapter."""

    def __init__(self, url: str = "sqlite:///./bancavoz.db"):
        self.url = url
        self.postgres = url.startswith(("postgres://", "postgresql://"))
        self.path = ""
        self._conn: sqlite3.Connection | None = None
        self._lock = Lock()
        if not self.postgres:
            if not url.startswith("sqlite:///"):
                raise ValueError("DATABASE_URL must be sqlite:/// or postgresql://")
            raw = url.removeprefix("sqlite:///")
            self.path = ":memory:" if raw in (":memory:", "") else str(Path(raw))

    def _connect_postgres(self):
        try:
            import psycopg  # type: ignore[import-not-found]
            from psycopg.rows import dict_row  # type: ignore[import-not-found]
        except ImportError as exc:
            raise RuntimeError("psycopg is required for PostgreSQL deployments") from exc
        return psycopg.connect(self.url, row_factory=dict_row)

    def connect(self) -> None:
        if self.postgres:
            with self.transaction():
                return
        with self._lock:
            if self._conn is None:
                self._conn = sqlite3.connect(self.path, check_same_thread=False)
                self._conn.row_factory = sqlite3.Row
                self._conn.execute("PRAGMA foreign_keys=ON")
                self._conn.executescript(SQLITE_SCHEMA)
                self._conn.commit()

    def migrations(self) -> None:
        """Apply the idempotent schema migrations for the configured backend."""
        self.connect()

    @contextmanager
    def transaction(self) -> Iterator[ConnectionAdapter]:
        if self.postgres:
            raw = self._connect_postgres()
            adapter = ConnectionAdapter(raw, True)
            try:
                for statement in POSTGRES_SCHEMA.split(";"):
                    if statement.strip():
                        raw.execute(statement)
                yield adapter
                raw.commit()
            except Exception:
                raw.rollback()
                raise
            finally:
                raw.close()
            return
        self.connect()
        assert self._conn is not None
        try:
            yield ConnectionAdapter(self._conn, False)
            self._conn.commit()
        except Exception:
            self._conn.rollback()
            raise

    def ensure_merchant(self, merchant_id: str, token: str) -> None:
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        with self.transaction() as conn:
            conn.execute(
                """INSERT INTO merchants(id, token_hash) VALUES(?, ?)
                   ON CONFLICT(id) DO NOTHING""",
                (merchant_id, token_hash),
            )

    def merchant_for_token(self, token: str) -> str | None:
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        with self.transaction() as conn:
            row = conn.execute(
                "SELECT id, token_hash FROM merchants WHERE active=1 AND token_hash=?",
                (token_hash,),
            ).fetchone()
        if not row:
            return None
        import hmac
        return str(row["id"]) if hmac.compare_digest(str(row["token_hash"]), token_hash) else None

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None
