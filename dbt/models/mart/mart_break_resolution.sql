-- mart_break_resolution
-- SLA tracking for break resolution
-- Joins break_resolutions table with break_report for full context

SELECT
    br.break_id,
    br.trade_id,
    br.break_type,
    br.priority,
    br.status,
    br.detected_at,
    br.resolved_at,
    br.resolved_by,
    br.resolution_note,

    -- Time metrics
    CASE
        WHEN br.resolved_at IS NOT NULL
        THEN ROUND(EXTRACT(EPOCH FROM (br.resolved_at - br.detected_at)) / 3600.0, 1)
        ELSE ROUND(EXTRACT(EPOCH FROM (NOW() - br.detected_at)) / 3600.0, 1)
    END                                         AS hours_open,

    -- SLA target by priority (hours)
    CASE br.priority
        WHEN 'HIGH'   THEN 4
        WHEN 'MEDIUM' THEN 24
        WHEN 'LOW'    THEN 72
    END                                         AS sla_target_hours,

    -- SLA status
    CASE
        WHEN br.status = 'RESOLVED'
             AND EXTRACT(EPOCH FROM (br.resolved_at - br.detected_at)) / 3600.0
                 <= CASE br.priority WHEN 'HIGH' THEN 4 WHEN 'MEDIUM' THEN 24 ELSE 72 END
        THEN 'MET'
        WHEN br.status = 'RESOLVED'
        THEN 'BREACHED'
        WHEN EXTRACT(EPOCH FROM (NOW() - br.detected_at)) / 3600.0
             > CASE br.priority WHEN 'HIGH' THEN 4 WHEN 'MEDIUM' THEN 24 ELSE 72 END
        THEN 'BREACHED'
        ELSE 'ON_TRACK'
    END                                         AS sla_status

FROM {{ source('raw', 'break_resolutions') }} br
ORDER BY
    CASE br.priority WHEN 'HIGH' THEN 1 WHEN 'MEDIUM' THEN 2 ELSE 3 END,
    br.detected_at DESC