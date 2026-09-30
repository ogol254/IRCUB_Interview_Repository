-- Assumption: assessment has billing_period DATE (first day of billing month) for water bills.
WITH water_bills AS (
  SELECT wa.tariff_class, a.assessment_id, wa.account_no,
         date_trunc('month', a.billing_period)::date AS billing_month,
         a.amount_due
  FROM assessment a
  JOIN revenue_type rt ON rt.revenue_code=a.revenue_code AND rt.category='WATER'
  JOIN water_account wa ON wa.payer_id=a.payer_id
), paid_by_assessment AS (
  SELECT assessment_id, SUM(amount) AS collected
  FROM payment
  GROUP BY assessment_id
)
SELECT wb.tariff_class, wb.billing_month,
       SUM(wb.amount_due) AS total_billed,
       SUM(COALESCE(p.collected,0)) AS total_collected,
       ROUND(100.0*SUM(COALESCE(p.collected,0))/NULLIF(SUM(wb.amount_due),0),2) AS collection_efficiency_pct
FROM water_bills wb
LEFT JOIN paid_by_assessment p USING (assessment_id)
GROUP BY wb.tariff_class, wb.billing_month
ORDER BY wb.billing_month, wb.tariff_class;

-- Top 10 accounts with arrears older than 90 days.
WITH paid AS (
  SELECT assessment_id, SUM(amount) AS paid_amount FROM payment GROUP BY assessment_id
), arrears AS (
  SELECT wa.account_no, wa.payer_id,
         GREATEST(a.amount_due-COALESCE(p.paid_amount,0),0) AS outstanding
  FROM assessment a
  JOIN revenue_type rt ON rt.revenue_code=a.revenue_code AND rt.category='WATER'
  JOIN water_account wa ON wa.payer_id=a.payer_id
  LEFT JOIN paid p USING (assessment_id)
  WHERE a.due_date < CURRENT_DATE - INTERVAL '90 days'
    AND a.status IN ('OPEN','PART_PAID')
)
SELECT account_no, payer_id, SUM(outstanding) AS arrears_over_90_days
FROM arrears
GROUP BY account_no, payer_id
HAVING SUM(outstanding)>0
ORDER BY arrears_over_90_days DESC
LIMIT 10;
