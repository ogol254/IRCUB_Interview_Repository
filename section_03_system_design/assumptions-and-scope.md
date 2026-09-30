# Assumptions and scope

## In scope

Design strictly>60-day unpaid tax/water detection, notices with secure link/reference, strictly>90-day tax escalation, independent payment-plan approval, enforcement pause/resumption, water notices/work orders, full-payment cancellation/reconnection and traceable audit/reconciliation. One active case tracks one obligation; multiple water accounts remain distinct.

## Out of scope

Implementation of this module and the Section2 POC; court processes; legislation; physical valve automation; national identity integration; production identity/role provisioning; exchange rates; write-off/reversal workflows; analytics; customer-registration UI. Proposed role responsibilities do not imply delivered role-management software.

## Proposed policy assumptions

| ID | Assumption requiring approval | Consequence |
|---|---|---|
| A-01 | Agency business date uses Africa/Nairobi | Calendar day60/90 is excluded; day61/91 triggers |
| A-02 | Water notice defaults14calendar days from confirmed delivery | Failed delivery blocks automatic disconnection and enters review |
| A-03 | Plan approver differs from proposer | Pending request never pauses enforcement |
| A-04 | Default grace is3calendar days | Check settled allocations/provider status before declaring default |
| A-05 | Agency defines whether penalties/reconnection fees form full-payment debt | Quote is versioned; no silent waiver |
| A-06 | Providers authenticate settled callbacks; FMIS honours immutable batch IDs/lookup | Redirect or timeout alone cannot prove settlement/posting |
| A-07 | Payment link is opaque, expires24hours and contains no payer identity | Expiry requires verified reissue; link cannot edit payer details |
| A-08 | Audit retention is7years plus lawful hold | Confirm applicable policy and lawful basis before production |

Dependencies: verified payer contacts, authoritative ledger, jurisdiction/policy owners, OIDC identity provider, payment verification and statement API, SMS/email delivery receipts, FMIS idempotency/lookup, field device connectivity, observability and backups.

Constraints: intermittent field connectivity; low-bandwidth payer devices; segregated approvals; numeric money; synthetic interview data. SMS/FMIS outages cannot lose cases/payments. Offline field evidence is a draft until server validation; a stale downloaded order cannot override settled debt.
