-- int_mismatched_trades
-- Trades that exist on BOTH sides but have price or quantity differences

SELECT
    b.trade_id,
    b.symbol,
    b.side,
    b.traded_at,

    -- Broker side
    b.price                             AS broker_price,
    b.quantity                          AS broker_qty,

    -- Exchange side
    e.price                             AS exchange_price,
    e.quantity                          AS exchange_qty,

    -- Differences
    ABS(b.price - e.price)              AS price_diff,
    ABS(b.quantity - e.quantity)        AS qty_diff,

    -- Break classification
    CASE
        WHEN b.price    != e.price
         AND b.quantity != e.quantity   THEN 'PRICE_AND_QTY_MISMATCH'
        WHEN b.price    != e.price      THEN 'PRICE_MISMATCH'
        WHEN b.quantity != e.quantity   THEN 'QTY_MISMATCH'
    END AS break_type,

    -- Priority based on price difference magnitude
    {{ classify_priority('ABS(b.price - e.price)') }} AS priority

FROM {{ ref('stg_broker_trades') }} b
INNER JOIN {{ ref('stg_exchange_trades') }} e
    ON b.trade_id = e.trade_id
WHERE
    b.price    != e.price
    OR b.quantity != e.quantity