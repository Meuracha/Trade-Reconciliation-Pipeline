-- mart_break_report
-- Full list of all breaks for the Operations team dashboard

-- Price / qty mismatches
SELECT
    trade_id,
    symbol,
    side,
    traded_at,
    break_type,
    priority,
    broker_value,
    exchange_value,
    difference,
    break_category,
    CASE priority
        WHEN 'HIGH'   THEN 1
        WHEN 'MEDIUM' THEN 2
        WHEN 'LOW'    THEN 3
    END AS priority_order
FROM (
    SELECT
        trade_id,
        symbol,
        side,
        traded_at,
        break_type,
        priority,
        broker_price        AS broker_value,
        exchange_price      AS exchange_value,
        price_diff          AS difference,
        'PRICE/QTY'         AS break_category
    FROM {{ ref('int_mismatched_trades') }}

    UNION ALL

    SELECT
        trade_id,
        symbol,
        side,
        traded_at,
        break_type,
        priority,
        price               AS broker_value,
        NULL                AS exchange_value,
        NULL                AS difference,
        'MISSING'           AS break_category
    FROM {{ ref('int_missing_trades') }}
) all_breaks
ORDER BY priority_order, traded_at
