-- PostgreSQL. Parameters: :fy_start and :fy_end (exclusive end).
-- Produces every revenue type x Q1..Q4, including zero-collection quarters.
WITH quarters AS (
    SELECT generate_series(1,4) AS quarter_no
), revenue_quarters AS (
    SELECT r.revenue_code, r.name, q.quarter_no
    FROM revenue_type r CROSS JOIN quarters q
    WHERE r.is_active = TRUE
), aggregated AS (
    SELECT p.revenue_code,
           ((EXTRACT(MONTH FROM age(p.paid_at::date, :fy_start::date))::int / 3) + 1) AS quarter_no,
           SUM(p.amount) AS quarter_total
    FROM payment p
    WHERE p.paid_at >= :fy_start AND p.paid_at < :fy_end
    GROUP BY p.revenue_code, quarter_no
), complete AS (
    SELECT rq.revenue_code, rq.name, rq.quarter_no,
           COALESCE(a.quarter_total,0)::numeric AS quarter_total
    FROM revenue_quarters rq
    LEFT JOIN aggregated a USING (revenue_code, quarter_no)
)
SELECT revenue_code, name, quarter_no, quarter_total,
       SUM(quarter_total) OVER (
           PARTITION BY revenue_code ORDER BY quarter_no
           ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
       ) AS running_total,
       ROUND(100.0 * quarter_total /
             NULLIF(SUM(quarter_total) OVER (PARTITION BY quarter_no),0), 2) AS quarter_share_pct
FROM complete
ORDER BY revenue_code, quarter_no;

-- Recommended indexes / physical design for ~50M payments:
CREATE INDEX IF NOT EXISTS ix_payment_paidat_revenue
    ON payment (paid_at, revenue_code) INCLUDE (amount);
CREATE UNIQUE INDEX IF NOT EXISTS ux_payment_external_ref
    ON payment (external_ref);
-- At this volume, range-partition payment by paid_at (monthly/quarterly) so FY scans prune partitions.
