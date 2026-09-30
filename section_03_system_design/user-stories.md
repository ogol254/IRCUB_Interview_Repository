# Four assessment user stories

## US-01 Payer receives an overdue notification

As a payer, I want a clear overdue notice with my payment reference and a secure way to pay, so that I can settle my debt and avoid further action.

- Given unpaid debt is 61 days overdue and verified contacts exist, when detection runs, then one case and SMS/email notice are queued with amount, reference, due date and assistance route (FR-001–006).
- Given a valid link, when I review and settle the current quoted balance, then verified allocation produces a receipt and pauses/cancels eligible enforcement after commit (FR-016/020).
- Given the link expired or balance changed, when I open/submit it, then I receive a verified reissue/refreshed quote; no stale amount is silently charged.
- Given SMS delivery fails permanently, when retries finish, then the case enters officer review and disconnection notice eligibility is not assumed.

## US-02 Auditor reviews escalated cases

As an auditor, I want to review escalations and their supporting evidence, so that I can assess lawful, consistent enforcement without altering financial records.

- Given a tax debt is 91 days overdue, when escalation runs, then the auditor sees debt, assigned officer, notices, rule version and decision history (FR-007/008/021).
- Given read-only auditor access, when a balance/assignment mutation is attempted, then the API denies it and records the denied action.
- Given missing delivery or assignment evidence, when the auditor reviews the case, then the gap is visible and can be referred for review without inventing evidence.

## US-03 Administrator configures rules

As an administrator, I want to version notice and escalation rules, so that agencies can apply approved policy consistently and explain each decision.

- Given approval to change a water notice period, when I save a future effective date and valid period, then a new version is created and eligible future notices use it (FR-010).
- Given inconsistent thresholds, a zero/negative notice period or missing effective date, when I submit, then validation rejects the configuration and leaves the active version intact.
- Given cases already carry a notice version, when a new version starts, then existing notices are not retroactively shortened; a policy-approved reissue is required.
- Given persistence fails, when I save, then no partially active version exists and I receive a correlation ID for support.

## US-04 Water field officer closes an order

As a water field officer, I want to view and close my assigned disconnection or reconnection order with evidence, so that the service state and audit trail reflect the action taken.

- Given an assigned eligible order and online version check, when I complete the action with time/outcome/evidence, then the order closes once and the service state changes transactionally (FR-018).
- Given a full payment cancelled my downloaded order, when I attempt completion, then the server rejects the stale version and tells me not to disconnect.
- Given I have no connectivity, when I capture evidence, then it remains a pending local draft; it is not represented as server-approved completion.
- Given disconnection already completed and settlement approved, when I close a reconnection order, then the original disconnection evidence remains and the account returns to active service.
