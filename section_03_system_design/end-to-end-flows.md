# Six end-to-end flows

Business flow overview: [SVG](diagrams/business-flows.svg). Proposed design only.

## Flow 1 — debt becomes more than60days overdue

Snapshot agency date; scan unpaid obligations with due_date < date−60. Lock/recheck settled balance; upsert one case and write notification outbox in one transaction. Worker sends SMS/email with opaque expiring link/reference; retain delivery receipts. Retry transient delivery errors; permanent/missing contacts enter officer review. Undelivered notice is not evidence of service.

## Flow 2 — tax becomes more than90days overdue

Recheck balance and approved holds. Create case/level escalation once; assign officer by jurisdiction/capacity. Auditor receives read-only access to debt, notice, rule and decision evidence. Failed assignment remains visible in an unassigned queue; auditor cannot amend balance.

## Flow 3 — water arrears to disconnection

Deliver notice; wait its recorded configured period. Lock/recheck balance, current plan/appeal hold and order state; create/assign one active work order. Field officer checks server eligibility before execution. If payment wins the row-lock race, cancel order; if physical disconnection is already underway, dispatcher reviews safe action/reconnection. No automatic erasure of completed field evidence.

## Flow 4 — approved plan pauses enforcement

Validate current debt quote, instalment sum and chronological dates. Independent supervisor rechecks debt and approves. One transaction activates plan, pauses case and cancels/holds unstarted orders, with audit/outbox. Proposed or failed approval alone never pauses enforcement.

## Flow 5 — default resumes enforcement

After grace, check settled allocations and pending provider status. Lock plan/case, record default once and resume enforcement with recorded policy. Notify payer and recheck notice eligibility before issuing a new order; never duplicate active orders. Later payments update the current balance and eligibility.

## Flow 6 — full mobile-money payment after notice

1. Customer opens secure link and refreshes debt quote/reference, including approved penalties/fees.
2. Mobile-money provider settles; browser redirect is informational.
3. API verifies HMAC/time/idempotency; unknown references go to suspense review.
4. Lock obligation/account/order; allocate settled money once and recheck full-payment policy.
5. In one transaction clear debt/case, cancel pending disconnection and append audit/outbox events. Already completed disconnection preserves evidence and generates reconnection review/order.
6. After commit notify dispatch/field tablet and customer. Notification/FMIS outages cannot keep settled debt under enforcement.
7. Journal worker claims unposted payments, groups date/currency/revenue→GL, persists immutable batch/lines/membership and checks debit=credit.
8. POST stable batch ID; retry408/429/5xx/network up to3attempts with backoff. Permanent errors enter manual review. Accepted-timeout requires same-key retry or lookup, never a new batch.
9. Store FMIS reference. Reconcile provider→IRCUB→FMIS by date/currency/GL/count/amount and drill through external_ref/payment_id/batch_id. Exceptions need owner, age and evidence; no balancing plug journal.
10. Customer sees payment receipt promptly, with financial-posting status separate.

[Simple business diagram](diagrams/full-payment-business.svg) and [technical sequence](diagrams/full-payment-sequence.svg). Section1 demonstrates callback controls, single-assessment principal allocation, journal/retry and mock reconciliation. Secure payer links, compliance cancellation, notifications and reconnection remain Section3 design.
