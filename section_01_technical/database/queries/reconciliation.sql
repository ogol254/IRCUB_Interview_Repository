-- Local mock reconciliation: identifies missing, extra and changed batch membership.
WITH local_totals AS (
 SELECT b.batch_id,b.business_date,b.currency,count(p.payment_id) payment_count,sum(p.amount) ledger_amount,
 (SELECT sum(credit) FROM fmis_batch_line l WHERE l.batch_id=b.batch_id) journal_amount
 FROM fmis_batch b JOIN payment p USING(batch_id) GROUP BY b.batch_id
), remote AS (
 SELECT j.batch_id,j.reference,(j.journal->>'business_date')::date business_date,j.journal->>'currency' currency,
 (SELECT sum((line->>'credit')::numeric) FROM jsonb_array_elements(j.journal->'lines') line) fmis_amount
 FROM mock_fmis_journal j
)
SELECT coalesce(l.batch_id,r.batch_id) batch_id,l.business_date,l.currency,l.payment_count,l.ledger_amount,l.journal_amount,r.fmis_amount,r.reference,
 CASE WHEN l.batch_id IS NULL THEN 'EXTRA_FMIS' WHEN r.batch_id IS NULL THEN 'MISSING_FMIS'
 WHEN l.ledger_amount<>r.fmis_amount OR l.journal_amount<>r.fmis_amount OR l.business_date<>r.business_date OR l.currency<>r.currency THEN 'MISMATCH' ELSE 'MATCH' END status
FROM local_totals l FULL JOIN remote r USING(batch_id);

-- GL drill-down, including GLs present on only one side.
WITH local_gl AS (
 SELECT b.batch_id,b.business_date,b.currency,l.gl_code,sum(l.credit) credit FROM fmis_batch b JOIN fmis_batch_line l USING(batch_id) WHERE l.credit>0 GROUP BY b.batch_id,l.gl_code
), remote_gl AS (
 SELECT j.batch_id,line->>'gl_code' gl_code,sum((line->>'credit')::numeric) credit FROM mock_fmis_journal j CROSS JOIN LATERAL jsonb_array_elements(j.journal->'lines') line WHERE (line->>'credit')::numeric>0 GROUP BY j.batch_id,line->>'gl_code'
)
SELECT coalesce(l.batch_id,r.batch_id) batch_id,coalesce(l.gl_code,r.gl_code) gl_code,l.credit ircub_credit,r.credit fmis_credit,
 CASE WHEN l.credit IS DISTINCT FROM r.credit THEN 'MISMATCH' ELSE 'MATCH' END status FROM local_gl l FULL JOIN remote_gl r USING(batch_id,gl_code);

SELECT payment_id,external_ref,amount,currency,revenue_code,batch_id,fmis_status FROM payment ORDER BY paid_at;
