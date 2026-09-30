BEGIN;
CREATE FUNCTION quarterly_collections(fy_start date, fy_end date) RETURNS TABLE(revenue_code text,name text,quarter_no int,quarter_total numeric,running_total numeric,quarter_share_pct numeric) LANGUAGE plpgsql AS $$
BEGIN
 IF fy_end<> (fy_start+interval '1 year')::date THEN RAISE EXCEPTION 'Financial year must span one calendar year'; END IF;
 RETURN QUERY WITH quarters AS (
 SELECT n, fy_start + (n-1)*interval '3 months' AS starts, fy_start+n*interval '3 months' AS ends FROM generate_series(1,4) n
 ), totals AS (
 SELECT r.revenue_code,r.name,q.n,coalesce(sum(p.amount),0) total FROM revenue_type r CROSS JOIN quarters q
 LEFT JOIN payment p ON p.revenue_code=r.revenue_code AND p.paid_at>=q.starts AT TIME ZONE 'UTC' AND p.paid_at<q.ends AT TIME ZONE 'UTC'
 GROUP BY r.revenue_code,r.name,q.n)
 SELECT t.revenue_code,t.name,t.n,t.total,sum(t.total) OVER(PARTITION BY t.revenue_code ORDER BY t.n),
 coalesce(round(100*t.total/nullif(sum(t.total) OVER(PARTITION BY t.n),0),2),0) FROM totals t ORDER BY t.revenue_code,t.n;
END $$;
CREATE FUNCTION collection_efficiency(as_of timestamptz) RETURNS TABLE(tariff_class text,billing_month date,total_billed numeric,total_collected numeric,efficiency_pct numeric) LANGUAGE sql AS $$
 WITH paid AS (SELECT assessment_id,sum(amount) collected FROM payment WHERE paid_at<=as_of GROUP BY assessment_id)
 SELECT wa.tariff_class,date_trunc('month',a.billing_period)::date,sum(a.amount_due),sum(coalesce(p.collected,0)),round(100*sum(coalesce(p.collected,0))/nullif(sum(a.amount_due),0),2)
 FROM assessment a JOIN water_account wa ON wa.account_no=a.account_no JOIN revenue_type r USING(revenue_code)
 LEFT JOIN paid p USING(assessment_id) WHERE r.category='WATER' AND a.billing_period<=as_of::date GROUP BY wa.tariff_class,date_trunc('month',a.billing_period)::date;
$$;
CREATE FUNCTION water_arrears(as_of date) RETURNS TABLE(account_no text,payer_id bigint,arrears numeric) LANGUAGE sql AS $$
 WITH paid AS (SELECT assessment_id,sum(amount) collected FROM payment WHERE paid_at<(as_of+1)::timestamp AT TIME ZONE 'UTC' GROUP BY assessment_id)
 SELECT a.account_no,a.payer_id,sum(greatest(a.amount_due-coalesce(p.collected,0),0)) outstanding FROM assessment a JOIN revenue_type r USING(revenue_code) LEFT JOIN paid p USING(assessment_id)
 WHERE r.category='WATER' AND a.account_no IS NOT NULL AND a.due_date<as_of-90 GROUP BY a.account_no,a.payer_id HAVING sum(greatest(a.amount_due-coalesce(p.collected,0),0))>0 ORDER BY outstanding DESC,a.account_no LIMIT 10;
$$;
CREATE TABLE penalty_history(id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,assessment_id bigint NOT NULL REFERENCES assessment,penalty_date date NOT NULL,overdue_months int NOT NULL,unpaid_amount numeric(18,2) NOT NULL,calculated_penalty numeric(18,2) NOT NULL,created_at timestamptz NOT NULL DEFAULT now(),UNIQUE(assessment_id,penalty_date));
CREATE PROCEDURE apply_overdue_penalties(run_date date) LANGUAGE plpgsql AS $$
DECLARE a record; months int; unpaid numeric; penalty numeric;
BEGIN
 FOR a IN SELECT * FROM assessment WHERE status<>'PAID' AND due_date<run_date ORDER BY assessment_id FOR UPDATE LOOP
  -- Started monthly anniversaries: day 1..first anniversary = month 1.
  months:=extract(year FROM age(run_date,a.due_date))::int*12+extract(month FROM age(run_date,a.due_date))::int;
  IF a.due_date+make_interval(months=>months)<run_date THEN months:=months+1; END IF;
  SELECT greatest(a.amount_due-coalesce(sum(amount),0),0) INTO unpaid FROM payment WHERE assessment_id=a.assessment_id AND paid_at<(run_date+1)::timestamp AT TIME ZONE 'UTC';
  penalty:=round(least(a.amount_due,unpaid*(least(months,3)*0.05+greatest(months-3,0)*0.10)),2);
  INSERT INTO penalty_history(assessment_id,penalty_date,overdue_months,unpaid_amount,calculated_penalty) VALUES(a.assessment_id,run_date,months,unpaid,penalty) ON CONFLICT DO NOTHING;
  IF FOUND THEN UPDATE assessment SET penalty_amount=penalty WHERE assessment_id=a.assessment_id; END IF;
 END LOOP;
END $$;
COMMIT;
