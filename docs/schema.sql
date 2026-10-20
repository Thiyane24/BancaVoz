-- PostgreSQL deployment schema. The SQLite adapter uses the equivalent schema
-- embedded in bancavoz.db for zero-setup tests.
CREATE TABLE IF NOT EXISTS ledger_entries (
    id BIGSERIAL PRIMARY KEY,
    merchant_id TEXT NOT NULL,
    idempotency_key TEXT NOT NULL,
    entry_type TEXT NOT NULL,
    amount_minor BIGINT NOT NULL CHECK (amount_minor >= 0),
    currency CHAR(3) NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    party TEXT,
    quantity INTEGER NOT NULL DEFAULT 0,
    unit_price_minor BIGINT,
    product TEXT,
    metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    reversed_entry_id BIGINT REFERENCES ledger_entries(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (merchant_id, idempotency_key)
);
CREATE INDEX IF NOT EXISTS idx_entries_merchant_time ON ledger_entries (merchant_id, created_at);
CREATE INDEX IF NOT EXISTS idx_entries_merchant_product ON ledger_entries (merchant_id, product);
