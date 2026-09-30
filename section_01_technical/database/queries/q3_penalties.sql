BEGIN;
CALL apply_overdue_penalties('2026-09-30');
COMMIT;
SELECT * FROM penalty_history ORDER BY assessment_id,penalty_date;
