# Functional requirements

“Must” below is design intent, not an implementation claim. Thresholds 60 and 90 days come from the assessment; notice and grace defaults are assumptions A-02/A-04.

| ID | Requirement and acceptance measure |
|---|---|
| FR-001 | Daily scan flags tax assessments with unpaid eligible balance and age >60 days; day 60 is excluded. Re-running creates no duplicate active case. |
| FR-002 | Daily scan flags water arrears >60 days, linked to the actual account and obligation; multiple accounts for one payer remain distinct. |
| FR-003 | Case records obligation reference, debt snapshot, current balance, rule version and detection time; cleared balances close rather than delete cases. |
| FR-004 | Queue SMS and email notices to verified contacts with reference, amount, due date, reason and support route. Each attempt and delivery receipt is retained; retry transient gateway failures, send permanent failure to review. |
| FR-005 | Issue an opaque, expiring, rate-limited secure link to the payer's own debt quote. No TIN/contact data in URL. Quote expiry or balance change requires refresh before payment. |
| FR-006 | Payment reference uniquely resolves the obligation; callbacks validate provider identity, timestamp, signature and idempotency before allocation. Unknown references enter suspense/manual review. |
| FR-007 | At tax age >90 days, create a unique escalation and assign a compliance officer by jurisdiction/capacity; day 90 is excluded. Reassignment retains history. |
| FR-008 | Auditor has read-only access to escalations, notices, allocation history and decision evidence; cannot change balances or approve own activity. |
| FR-009 | Water notice includes proposed disconnection date and appeal/payment-plan route. Work order eligibility requires proven delivery and expired configured notice period. |
| FR-010 | Administrator versions thresholds, templates, notice/grace periods and effective dates within agency policy limits; reject invalid ordering and unauthorised edits. No silent retroactive enforcement. |
| FR-011 | Generate one active disconnection work order per account/case after a transactional check of current debt, plan pause and notice eligibility. |
| FR-012 | Payer/officer can propose a payment plan with instalments whose sum equals eligible debt and monotonically ordered dates. Proposal records debt version and terms. |
| FR-013 | Independent supervisor approves/rejects the plan with reasons and recorded actor/time. Approval rechecks balance and recalculates terms if debt changed. |
| FR-014 | Approved current plan atomically pauses case enforcement and cancels/holds unstarted disconnection work; emergency or already executing work goes to dispatcher review. |
| FR-015 | Allocations update instalment balances. After configured default grace, engine resumes enforcement using the recorded rule and issues a default notice; no duplicate work order. |
| FR-016 | Settled full payment atomically clears debt/case and cancels pending work orders. Partial payment recalculates balance but does not imply clearance. |
| FR-017 | If disconnection already completed, raise a reconnection request after policy checks. Preserve the completed order and its evidence. |
| FR-018 | Field officer sees only assigned orders; validates current order version online before dispatch/completion, records time, outcome and evidence. Cancelled/stale orders cannot be completed. |
| FR-019 | Generate balanced daily journals from allocated successful collections, persist batch membership, post with stable batch ID and reconcile provider→IRCUB→FMIS by date/currency/GL. |
| FR-020 | Send customer settlement confirmation after allocation commit; disclose FMIS pending separately. FMIS outage does not keep a paid account under enforcement. |
| FR-021 | Append actor, timestamp, correlation ID, policy version and before/after state for each case/plan/work-order/financial decision. Export protected audit evidence. |
| FR-022 | Failed jobs remain durable with next attempt, reason and owner; operational review includes undelivered notices, unknown payments, stalled work orders and FMIS failures. |
| FR-023 | Authorised officers can resolve disputes through a reasoned hold with expiry and independent approval; all holds are visible to auditors. This is proposed scope subject to agency approval. |

State transitions: case OPEN → NOTIFIED → ESCALATED or NOTICE_ACTIVE → PAUSED_PLAN → RESUMED → CLEARED. Work order PENDING → ASSIGNED → IN_PROGRESS → COMPLETED, or CANCELLED before execution; an IN_PROGRESS race goes to REVIEW. Plan PROPOSED → APPROVED → ACTIVE → COMPLETED or DEFAULTED; rejection never pauses enforcement.
