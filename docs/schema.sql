-- Source-of-truth local/test schema.
-- This file mirrors bancavoz/db.py exactly as of the documented verification.
-- The application currently rejects PostgreSQL URLs; no PostgreSQL migration
-- runner or merchants/digests tables are implemented yet.

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
    request_hash TEXT,
    UNIQUE (merchant_id, idempotency_key),
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
    PRIMARY KEY (merchant_id, product)
);

-- Current limitation: expense category is stored in ledger_entries.product.
-- merchants and digests are requirements, not current database objects.
