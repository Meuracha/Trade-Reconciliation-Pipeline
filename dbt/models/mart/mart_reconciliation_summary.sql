-- mart_reconciliation_summary
-- Daily high-level reconciliation KPIs

WITH matched AS (
    SELECT COUNT(*) AS cnt FROM {{ ref('int_matched_trades') }}
),
mismatched AS (
    SELECT COUNT(*) AS cnt FROM {{ ref('int_mismatched_trades') }}
),
missing AS (
    SELECT COUNT(*) AS cnt FROM {{ ref('int_missing_trades') }}
),
totals AS (
    SELECT
        matched.cnt                             AS matched_count,
        mismatched.cnt + missing.cnt            AS break_count,
        matched.cnt + mismatched.cnt + missing.cnt AS total_trades
    FROM matched, mismatched, missing
)

SELECT
    CURRENT_DATE                            AS summary_date,
    total_trades,
    matched_count,
    break_count                             AS total_breaks,
    ROUND(
        matched_count::NUMERIC / NULLIF(total_trades, 0) * 100, 2
    )                                       AS match_rate,
    CASE
        WHEN ROUND(matched_count::NUMERIC / NULLIF(total_trades, 0) * 100, 2) >= 99 THEN 'GOOD'
        WHEN ROUND(matched_count::NUMERIC / NULLIF(total_trades, 0) * 100, 2) >= 95 THEN 'WARNING'
        ELSE 'CRITICAL'
    END                                     AS status
FROM totals