-- 1. Assignment balance and sample-ratio check
SELECT
    variant,
    COUNT(*) AS assigned_users,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2) AS assignment_share_pct
FROM experiment_assignments
GROUP BY variant
ORDER BY variant;

-- 2. Experiment scorecard by assigned variant
SELECT
    a.variant,
    COUNT(DISTINCT a.user_id) AS users,
    COUNT(s.session_id) AS search_sessions,
    ROUND(AVG(s.successful_search) * 100, 2) AS successful_search_rate_pct,
    ROUND(AVG(s.clicked_result) * 100, 2) AS click_through_rate_pct,
    ROUND(AVG(s.zero_results) * 100, 2) AS zero_result_rate_pct,
    ROUND(AVG(s.search_error) * 100, 2) AS search_error_rate_pct,
    ROUND(AVG(s.watch_minutes_after_search), 2) AS avg_watch_minutes
FROM experiment_assignments AS a
JOIN search_sessions AS s
    ON a.user_id = s.user_id
GROUP BY a.variant
ORDER BY a.variant;

-- 3. User-level primary metric for valid inference at the randomization unit
WITH user_metrics AS (
    SELECT
        a.user_id,
        a.variant,
        COUNT(*) AS search_sessions,
        AVG(s.successful_search) AS user_success_rate,
        AVG(s.clicked_result) AS user_click_through_rate,
        AVG(s.search_error) AS user_error_rate
    FROM experiment_assignments AS a
    JOIN search_sessions AS s
        ON a.user_id = s.user_id
    GROUP BY a.user_id, a.variant
)
SELECT
    variant,
    COUNT(*) AS users,
    ROUND(AVG(user_success_rate) * 100, 2) AS mean_user_success_rate_pct,
    ROUND(AVG(user_click_through_rate) * 100, 2) AS mean_user_click_through_rate_pct,
    ROUND(AVG(user_error_rate) * 100, 2) AS mean_user_error_rate_pct
FROM user_metrics
GROUP BY variant
ORDER BY variant;

-- 4. Daily experiment stability
SELECT
    s.search_date,
    a.variant,
    COUNT(*) AS search_sessions,
    ROUND(AVG(s.successful_search) * 100, 2) AS successful_search_rate_pct,
    ROUND(AVG(s.search_error) * 100, 2) AS search_error_rate_pct
FROM search_sessions AS s
JOIN experiment_assignments AS a
    ON s.user_id = a.user_id
GROUP BY s.search_date, a.variant
ORDER BY s.search_date, a.variant;

-- 5. Primary and guardrail metrics by platform
SELECT
    a.platform,
    a.variant,
    COUNT(DISTINCT a.user_id) AS users,
    COUNT(*) AS search_sessions,
    ROUND(AVG(s.successful_search) * 100, 2) AS successful_search_rate_pct,
    ROUND(AVG(s.search_error) * 100, 2) AS search_error_rate_pct
FROM experiment_assignments AS a
JOIN search_sessions AS s
    ON a.user_id = s.user_id
GROUP BY a.platform, a.variant
ORDER BY a.platform, a.variant;

-- 6. Search outcomes by query category
SELECT
    s.query_category,
    a.variant,
    COUNT(*) AS search_sessions,
    ROUND(AVG(s.successful_search) * 100, 2) AS successful_search_rate_pct,
    ROUND(AVG(s.zero_results) * 100, 2) AS zero_result_rate_pct,
    ROUND(AVG(s.watch_minutes_after_search), 2) AS avg_watch_minutes
FROM search_sessions AS s
JOIN experiment_assignments AS a
    ON s.user_id = a.user_id
GROUP BY s.query_category, a.variant
ORDER BY s.query_category, a.variant;
