-- int_matched_trades
-- Trades that exist on BOTH sides with matching price and quantity

SELECT
    b.trade_id,
    b.symbol,
    b.side,
    b.quantity,
    b.price,
    b.traded_at,
    'MATCHED' AS status
FROM {{ ref('stg_broker_trades') }} b
INNER JOIN {{ ref('stg_exchange_trades') }} e
    ON  b.trade_id = e.trade_id
    AND b.price    = e.price
    AND b.quantity = e.quantity