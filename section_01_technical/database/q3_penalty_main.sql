ALTER TABLE assessment ADD COLUMN IF NOT EXISTS penalty_amount numeric(18,2) NOT NULL DEFAULT 0;
CREATE TABLE IF NOT EXISTS penalty_history(
  penalty_history_id bigserial PRIMARY KEY,
  assessment_id bigint NOT NULL REFERENCES assessment(assessment_id),
  penalty_date date NOT NULL,
  overdue_months int NOT NULL,
  unpaid_amount numeric(18,2) NOT NULL,
  calculated_penalty numeric(18,2) NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE(assessment_id, penalty_date)
);

-- Daily recalculation: cumulative penalty is derived from current unpaid principal and overdue months.
-- Unique(assessment_id, penalty_date) + transaction makes same-day execution idempotent.
CREATE OR REPLACE PROCEDURE apply_overdue_penalties(p_run_date date)
LANGUAGE plpgsql AS $$
DECLARE r record; v_months int; v_unpaid numeric(18,2); v_penalty numeric(18,2);
BEGIN
  FOR r IN
    SELECT a.assessment_id,a.amount_due,a.due_date,
           GREATEST(a.amount_due-COALESCE(SUM(p.amount),0),0) unpaid
    FROM assessment a LEFT JOIN payment p ON p.assessment_id=a.assessment_id
    WHERE a.status IN ('OPEN','PART_PAID') AND a.due_date < p_run_date
    GROUP BY a.assessment_id,a.amount_due,a.due_date
  LOOP
    v_months := GREATEST(1,
      (EXTRACT(YEAR FROM age(p_run_date,r.due_date))*12 + EXTRACT(MONTH FROM age(p_run_date,r.due_date)))::int);
    v_unpaid := r.unpaid;
    v_penalty := LEAST(r.amount_due,
      v_unpaid * (LEAST(v_months,3)*0.05 + GREATEST(v_months-3,0)*0.10));

    INSERT INTO penalty_history(assessment_id,penalty_date,overdue_months,unpaid_amount,calculated_penalty)
    VALUES(r.assessment_id,p_run_date,v_months,v_unpaid,v_penalty)
    ON CONFLICT(assessment_id,penalty_date) DO NOTHING;

    IF FOUND THEN
      UPDATE assessment SET penalty_amount=v_penalty WHERE assessment_id=r.assessment_id;
    END IF;
  END LOOP;
END $$;
