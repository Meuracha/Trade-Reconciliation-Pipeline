-- assert_no_duplicate_breaks
-- Each trade_id should appear only once in the break report
-- Duplicates indicate a logic error in intermediate models

SELECT
    trade_id,
    COUNT(*) AS cnt
FROM {{ ref('mart_break_report') }}
GROUP BY trade_id
HAVING COUNT(*) > 1