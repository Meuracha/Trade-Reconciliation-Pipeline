-- assert_match_rate_above_90
-- Match rate must not drop below 90%
-- If it does, the pipeline or simulator likely has a bug

SELECT *
FROM {{ ref('mart_reconciliation_summary') }}
WHERE match_rate < 90