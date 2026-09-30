-- DESIGN-ONLY Section3 extension of the assessment foundation.
-- Not applied by Compose. This is a schema proposal, not a Section2 implementation.
CREATE TABLE enforcement_rule(
 rule_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 agency text NOT NULL, version int NOT NULL CHECK(version>0),
 detect_after_days int NOT NULL CHECK(detect_after_days>=0),
 escalate_after_days int NOT NULL CHECK(escalate_after_days>detect_after_days),
 notice_days int NOT NULL CHECK(notice_days>0), default_grace_days int NOT NULL CHECK(default_grace_days>=0),
 effective_from date NOT NULL, approved_by text NOT NULL, UNIQUE(agency,version)
);
CREATE TABLE overdue_case(
 case_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 assessment_id bigint NOT NULL REFERENCES assessment,
 rule_id bigint NOT NULL REFERENCES enforcement_rule,
 opened_at timestamptz NOT NULL DEFAULT now(), outstanding_snapshot numeric(18,2) NOT NULL CHECK(outstanding_snapshot>0),
 status text NOT NULL CHECK(status IN ('OPEN','NOTIFIED','ESCALATED','NOTICE_ACTIVE','PAUSED_PLAN','RESUMED','CLEARED','CLOSED')),
 version int NOT NULL DEFAULT 1 CHECK(version>0)
);
CREATE UNIQUE INDEX one_live_case_per_assessment ON overdue_case(assessment_id) WHERE status NOT IN ('CLEARED','CLOSED');
CREATE TABLE notification(
 notification_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 case_id bigint NOT NULL REFERENCES overdue_case, dedupe_key text NOT NULL UNIQUE,
 channel text NOT NULL CHECK(channel IN ('SMS','EMAIL')), destination_masked text NOT NULL,
 template_version text NOT NULL, status text NOT NULL CHECK(status IN ('PENDING','SENT','DELIVERED','FAILED')),
 attempts int NOT NULL DEFAULT 0 CHECK(attempts>=0), sent_at timestamptz, delivered_at timestamptz, provider_ref text,
 notice_expires_at timestamptz, link_token_hash text, link_expires_at timestamptz
);
CREATE TABLE escalation(
 escalation_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY, case_id bigint NOT NULL REFERENCES overdue_case,
 level int NOT NULL CHECK(level>0), assigned_officer_subject text, status text NOT NULL,
 escalated_at timestamptz NOT NULL DEFAULT now(), UNIQUE(case_id,level)
);
CREATE TABLE payment_plan(
 plan_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY, case_id bigint NOT NULL REFERENCES overdue_case,
 status text NOT NULL CHECK(status IN ('PROPOSED','APPROVED','ACTIVE','REJECTED','DEFAULTED','COMPLETED')),
 debt_version int NOT NULL, proposed_by text NOT NULL, approved_by text, approved_at timestamptz,
 total_amount numeric(18,2) NOT NULL CHECK(total_amount>0), defaulted_at timestamptz,
 CHECK(approved_by IS NULL OR approved_by<>proposed_by),
 CHECK(status NOT IN ('APPROVED','ACTIVE','COMPLETED') OR (approved_by IS NOT NULL AND approved_at IS NOT NULL))
);
CREATE TABLE payment_plan_instalment(
 instalment_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY, plan_id bigint NOT NULL REFERENCES payment_plan,
 sequence_no int NOT NULL CHECK(sequence_no>0), due_date date NOT NULL, amount numeric(18,2) NOT NULL CHECK(amount>0),
 UNIQUE(plan_id,sequence_no)
);
CREATE TABLE payment_allocation(
 payment_id uuid NOT NULL REFERENCES payment, assessment_id bigint NOT NULL REFERENCES assessment,
 instalment_id bigint REFERENCES payment_plan_instalment,
 amount numeric(18,2) NOT NULL CHECK(amount>0), PRIMARY KEY(payment_id,assessment_id)
);
-- Aggregate sum bounds and chronological instalments require locked service transactions
-- plus deferred DB integrity checks in implementation; plain CHECK cannot enforce sums across rows.
CREATE TABLE work_order(
 work_order_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY, case_id bigint NOT NULL REFERENCES overdue_case,
 type text NOT NULL CHECK(type IN ('DISCONNECT','RECONNECT')),
 status text NOT NULL CHECK(status IN ('PENDING','ASSIGNED','IN_PROGRESS','REVIEW','COMPLETED','CANCELLED')),
 assigned_officer_subject text, scheduled_at timestamptz, completed_at timestamptz, cancelled_at timestamptz,
 cancellation_reason text, evidence_uri text, version int NOT NULL DEFAULT 1 CHECK(version>0)
);
CREATE UNIQUE INDEX one_active_field_action ON work_order(case_id,type) WHERE status IN ('PENDING','ASSIGNED','IN_PROGRESS','REVIEW');
CREATE TABLE audit_record(
 audit_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY, case_id bigint REFERENCES overdue_case,
 entity_type text NOT NULL, entity_id text NOT NULL, action text NOT NULL, actor_subject text NOT NULL,
 occurred_at timestamptz NOT NULL DEFAULT now(), correlation_id uuid NOT NULL,
 before_json jsonb, after_json jsonb, previous_hash text, record_hash text
);
-- Production: application roles get INSERT/SELECT audit permissions only; signed daily export
-- anchors protect against privileged tampering. DDL alone does not make audit records immutable.
