-- PostgreSQL production schema. The application applies this idempotently at startup.
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
