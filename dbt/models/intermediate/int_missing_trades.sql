-- int_missing_trades
-- Trades that exist on ONE side only

-- On broker but NOT on exchange
SELECT
    b.trade_id,
    b.symbol,
    b.side,
    b.quantity,
    b.price,
    b.traded_at,
    'MISSING_FROM_EXCHANGE'     AS break_type,
    'HIGH'                      AS priority
FROM {{ ref('stg_broker_trades') }} b
LEFT JOIN {{ ref('stg_exchange_trades') }} e
    ON b.trade_id = e.trade_id
WHERE e.trade_id IS NULL

UNION ALL

-- On exchange but NOT on broker
SELECT
    e.trade_id,
    e.symbol,
    e.side,
    e.quantity,
    e.price,
    e.traded_at,
    'MISSING_FROM_BROKER'       AS break_type,
    'HIGH'                      AS priority
FROM {{ ref('stg_exchange_trades') }} e
LEFT JOIN {{ ref('stg_broker_trades') }} b
    ON e.trade_id = b.trade_id
WHERE b.trade_id IS NULL