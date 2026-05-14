-- stg_exchange_trades
-- Clean and standardise raw exchange trades
-- Incremental: only process new records since last run

{{ config(
    materialized='incremental',
    unique_key='trade_id',
    tags=['staging', 'daily']
) }}

SELECT
    trade_id,
    UPPER(TRIM(symbol))     AS symbol,
    UPPER(TRIM(side))       AS side,
    quantity,
    price,
    traded_at,
    ingested_at,
    'exchange'              AS source
FROM {{ source('raw', 'raw_exchange_trades') }}
WHERE
    trade_id  IS NOT NULL
    AND symbol   IS NOT NULL
    AND quantity > 0
    AND price    > 0

{% if is_incremental() %}
    AND ingested_at > (SELECT MAX(ingested_at) FROM {{ this }})
{% endif %}