-- ─────────────────────────────────────────
-- Trade Reconciliation DB — Initial Schema
-- ─────────────────────────────────────────

-- Raw trades from Broker side (Yuanta)
CREATE TABLE IF NOT EXISTS raw_broker_trades (
    trade_id        VARCHAR(36)     NOT NULL,
    symbol          VARCHAR(10)     NOT NULL,
    side            VARCHAR(4)      NOT NULL,   -- BUY / SELL
    quantity        INTEGER         NOT NULL,
    price           NUMERIC(10, 2)  NOT NULL,
    traded_at       TIMESTAMP       NOT NULL,
    ingested_at     TIMESTAMP       DEFAULT NOW()
);

-- Raw trades from Exchange side (SET)
CREATE TABLE IF NOT EXISTS raw_exchange_trades (
    trade_id        VARCHAR(36)     NOT NULL,
    symbol          VARCHAR(10)     NOT NULL,
    side            VARCHAR(4)      NOT NULL,
    quantity        INTEGER         NOT NULL,
    price           NUMERIC(10, 2)  NOT NULL,
    traded_at       TIMESTAMP       NOT NULL,
    ingested_at     TIMESTAMP       DEFAULT NOW()
);

-- Break resolution tracking (Operations team updates this)
CREATE TABLE IF NOT EXISTS break_resolutions (
    break_id        SERIAL          PRIMARY KEY,
    trade_id        VARCHAR(36)     NOT NULL,
    break_type      VARCHAR(30)     NOT NULL,
    priority        VARCHAR(10)     NOT NULL,   -- HIGH / MEDIUM / LOW
    detected_at     TIMESTAMP       DEFAULT NOW(),
    resolved_at     TIMESTAMP,
    resolved_by     VARCHAR(100),
    resolution_note TEXT,
    status          VARCHAR(20)     DEFAULT 'OPEN'  -- OPEN / IN_PROGRESS / RESOLVED
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_broker_trade_id   ON raw_broker_trades(trade_id);
CREATE INDEX IF NOT EXISTS idx_exchange_trade_id ON raw_exchange_trades(trade_id);
CREATE INDEX IF NOT EXISTS idx_broker_symbol     ON raw_broker_trades(symbol);
CREATE INDEX IF NOT EXISTS idx_exchange_symbol   ON raw_exchange_trades(symbol);
CREATE INDEX IF NOT EXISTS idx_break_status      ON break_resolutions(status);
CREATE INDEX IF NOT EXISTS idx_break_trade_id    ON break_resolutions(trade_id);