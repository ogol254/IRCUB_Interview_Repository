"""Update only authorised coloured answers; preserve original questions and tables.

Requires scripts/document-tools-requirements.txt. Keeps a source backup for repeatable
updates and verifies untouched paragraph/table XML after saving.
"""

from copy import deepcopy
from pathlib import Path
import json
import shutil
from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, RGBColor
from docx.opc.constants import RELATIONSHIP_TYPE as RT
from lxml import etree

target = Path("Farsight_Africa_IRCUB_Answered.docx")
backup = Path("docs/original-assessment.docx")
if not backup.exists():
    shutil.copy2(target, backup)
doc = Document(backup)
purple = RGBColor.from_string("7030A0")
answers = [
    (
        "I use a revenue-type",
        "PostgreSQL: quarterly_collections validates a one-year financial range and builds all revenue types × four quarters, including inactive historical revenue types. LEFT JOIN/COALESCE supplies zero collections; window sums produce cumulative revenue totals and quarter shares, with zero for an empty quarter. UTC boundaries use an exclusive end. Example: SELECT * FROM quarterly_collections('2026-01-01','2027-01-01'). The covering paid_at/revenue_code index supports range scans; external_ref is separately unique. For 50M rows, measure parallel scans, visibility-map coverage and partition pruning. Date partitioning requires a separate global reference registry because partition-local unique keys cannot enforce global external_ref uniqueness. The demo stays unpartitioned to preserve that guarantee.",
        [
            "section_01_technical/database/queries/q1_quarterly.sql",
            "section_01_technical/database/migrations/001_foundation.sql",
            "tests/test_database.py",
            "section_01_technical/database/README.md",
        ],
    ),
    (
        "I aggregate bills",
        "PostgreSQL: collection_efficiency aggregates payments per assessment before joining billed amounts. An explicit assessment.account_no prevents one payer’s multiple water accounts from multiplying bills. billing_period identifies the cohort; collections include allocated payments up to the selected as-of timestamp. The seeded domestic bill is 1000 with two payments (100 + 200): billed1000, collected300, efficiency30%. Its payer’s separate commercial account remains billed2000/collected0. water_arrears uses unpaid principal, strictly older than90 days, and returns the ten highest account balances with deterministic ties. Unallocated officer captures do not count toward a bill until allocated.",
        [
            "section_01_technical/database/queries/q2_efficiency.sql",
            "section_01_technical/database/seed/001_demo.sql",
            "tests/test_database.py",
            "section_01_technical/database/README.md",
        ],
    ),
    (
        "I add assessment.penalty_amount",
        "PostgreSQL procedure apply_overdue_penalties locks assessments in ID order and calculates unpaid principal as of the run date. Rate = min(months,3)×5% + max(months−3,0)×10%, capped at original principal. Assumption: started monthly anniversaries, with zero when not overdue; this is a cumulative snapshot on current unpaid principal, not compounding. UNIQUE(assessment_id,penalty_date) allows exactly one daily history insert; assessment updates only if that insert succeeds. History and update share the caller transaction. Allocation takes the same assessment lock. Tests cover first/third/fourth months, partial payments, cap, concurrent repeated execution and rollback. Run CALL apply_overdue_penalties('2026-09-30') twice and inspect history.",
        [
            "section_01_technical/database/queries/q3_penalties.sql",
            "section_01_technical/database/migrations/002_reporting_penalties.sql",
            "tests/test_database.py",
            "section_01_technical/database/README.md",
        ],
    ),
    (
        "Tariffs are injected",
        'Python/Decimal: WaterBillingService reads tariff bands/service charge from config.json. Marginal boundary amounts are 0→200,10→700,11→775,30→2200,31→2310. Confirmed five-digit rollover99990→15 yields25m³ and1825; unexplained lower/out-of-capacity readings are rejected. Estimated consumption averages the latest three actual consumption intervals without integer rounding; four chronological actual cumulative readings are needed, and estimated history is excluded. This interpretation of “last3 actual readings” is explicit and requires agency agreement. The API can load actual history by meter_no. POST /api/v1/water/calculate with {"previous":"99990","current":"15","rollover":true}; /docs gives a live demonstration. Tests include missing history, fractional estimation and configuration changes.',
        [
            "section_01_technical/backend/water_bill.py",
            "section_01_technical/backend/config.json",
            "tests/test_water_bill.py",
            "section_01_technical/backend/README.md",
        ],
    ),
    (
        "Validation checks positive amount",
        "Python/FastAPI: four bounded async workers validate amount precision/positivity, payer, active revenue, channel/currency and external reference. PostgreSQL UNIQUE(external_ref), not a Python set, protects concurrent submissions across request keys/processes. Each item transaction commits payment/allocation or a separate failed_payment with reasons, and its durable processing result. Assessment locks prevent over-allocation and foreign keys prevent payer/revenue mismatch. Requests are coordinated with database advisory locks; retry after partial bulk completion reuses committed item receipts. Backpressure and a request admission gate leave pool capacity for workers. Concurrent test submissions produce one acceptance and nineteen rejections for the same reference.",
        [
            "section_01_technical/backend/payment_processor.py",
            "section_01_technical/database/migrations/003_request_results.sql",
            "tests/test_api.py",
            "section_01_technical/backend/README.md",
        ],
    ),
    (
        "POST /api/v1/payments/callback accepts",
        "Python/FastAPI: real callback, JSON bulk and payment lookup endpoints use PostgreSQL persistence. Provider HMAC-SHA256 covers timestamp + dot + exact raw body; constant-time verification and ±300-second checks reject forged/stale callbacks. Same key/body returns the stored response; same key/changed payload or replay under another key returns409. Officer bulk capture uses a separate credential so provider secrets never enter React. Item summaries expose accepted/rejected reasons; invalid records are stored separately. Infrastructure failures return503 with a correlation ID and instruct unchanged-key retry. Structured logs omit credentials/full callback payloads. Swagger/OpenAPI are available at /docs and /openapi.json. Live smoke tests exercise signed callbacks, replay, lookup and concurrency.",
        [
            "section_01_technical/backend/payment_api.py",
            "tests/test_api.py",
            "scripts/smoke.py",
            "section_01_technical/backend/README.md",
        ],
    ),
    (
        "Successful daily payments are grouped",
        "Python/httpx: successful daily USD payments receive persistent batch membership, revenue-to-GL credit lines and a collection-bank debit. Decimal balance validation precedes posting. Batch ID/body stay unchanged across retries; mock FMIS persists one journal and returns the same reference after an accepted-but-timed-out response. At most three attempts with1s/2s backoff; retry408/429/5xx/timeouts/network, while400/401/403/422 go directly to FAILED/manual review. Attempts persist before HTTP and a payment cannot be claimed for a second batch. Reconciliation compares day/currency/batch/GL totals and flags missing, extra or mismatched FMIS records, then drills into payment/external references. Failed/ambiguous batches require evidence review, not a new journal ID.",
        [
            "section_01_technical/backend/fmis_service.py",
            "section_01_technical/backend/mock_fmis.py",
            "section_01_technical/database/queries/reconciliation.sql",
            "tests/test_fmis_cache.py",
            "section_01_technical/backend/README.md",
        ],
    ),
    (
        "I use cache-aside for derived",
        "Python/Redis cache-aside: quarterly keys include report namespace, committed database version, USD and financial-year dates; TTL60s. Cache misses calculate PostgreSQL totals and populate Redis. A database trigger changes the report version in the payment insert transaction, making older keys unreachable. Repeatable-read pairs version and totals, preventing a concurrent stale writer from repopulating a current key. Redis failures return database reports and are observable; financial posting never depends on Redis. Trade-off: one small version read per report and a global version-row write hotspot. Old keys expire rather than requiring unreliable post-commit deletion. Tests validate Redis hit/invalidation and unavailable-Redis fallback.",
        [
            "section_01_technical/backend/cache.py",
            "section_01_technical/database/migrations/001_foundation.sql",
            "tests/test_fmis_cache.py",
            "section_01_technical/backend/README.md",
        ],
    ),
    (
        "I use a responsive three-step",
        "React/TypeScript: a real API-connected three-step capture app searches TIN/phone/water account, displays payer summary and selects active revenue. Officers add/remove/edit multiple amount/channel/reference lines with a running USD total and client validation. Confirmation shows authoritative accepted/rejected results and server receipt IDs; only accepted amounts form the printable receipt. Loading/network/duplicate states are visible. An uncertain response keeps the exact key/body for safe retry. Large controls, focus states, labelled fields and responsive tablet layout support interview use. Component tests cover search, invalid amount, multiple lines, receipt, duplicate and server failure; Playwright uses the live API. Collections are unallocated, with allocation separately demonstrated by callbacks.",
        [
            "section_01_technical/frontend/src/App.tsx",
            "section_01_technical/frontend/src/api.ts",
            "section_01_technical/frontend/tests/App.test.tsx",
            "section_01_technical/frontend/tests/e2e/payment.spec.ts",
            "section_01_technical/frontend/README.md",
        ],
    ),
    (
        "The complete response covers",
        "Section3 is a proposed Revenue Compliance & Enforcement design, not an implemented POC. FR-001–023 define strictly>60-day tax/water detection, verified notice delivery, secure expiring links/references, strictly>90-day tax escalation, officer assignment and auditor read-only oversight. Water enforcement waits the configured notice period; approved plans pause enforcement, defaults resume it, and settled full payment cancels pending orders. Completed disconnection is preserved and leads to reconnection review. Rule versions, independent approval, current-order checks and append-only/protected-export audit evidence make decisions explainable. Proposed NFR targets include99.9% API availability, payment p95<1s at5000/min, RPO≤5min/RTO≤60min and WCAG2.2AA; these require production validation. Notice14days, default grace3days and retention7years are labelled assumptions requiring agency approval.\nThe model links payer→assessment/water account→overdue case→notification/escalation/payment plan/instalment/work order/audit; payment allocations retain settlement provenance. Four stories use As a/I want/So that and Given/When/Then happy, validation and exception cases. Business and technical architecture/ERD diagrams serve Ministry and engineering audiences; six flows and five actor journeys are supplied.\nFull mobile-money payment: refresh debt quote→settled signed callback→lock and allocate once→clear debt/cancel unstarted order plus audit/outbox in one transaction→confirm to payer/field officer→persist balanced batch→post stable ID to FMIS→store reference→reconcile provider/ledger/GL. FMIS or SMS outage does not keep paid debt under enforcement. Stale or already executing field orders require dispatcher review; a completed disconnection is never erased. The two business diagrams below summarise this process.",
        [
            "section_03_system_design/README.md",
            "section_03_system_design/functional-requirements.md",
            "section_03_system_design/non-functional-requirements.md",
            "section_03_system_design/data-model.md",
            "section_03_system_design/user-stories.md",
            "section_03_system_design/diagrams/full-payment-sequence.svg",
            "section_03_system_design/end-to-end-flows.md",
            "TEST-REPORT.md",
        ],
    ),
]


def text(p):
    return "".join(p.itertext())


def canonical(element):
    return etree.tostring(element, method="c14n")


changed = set()
section3 = None


def link(p, path):
    h = OxmlElement("w:hyperlink")
    h.set(qn("r:id"), p.part.relate_to(path, RT.HYPERLINK, is_external=True))
    r = OxmlElement("w:r")
    props = OxmlElement("w:rPr")
    colour = OxmlElement("w:color")
    colour.set(qn("w:val"), "7030A0")
    props.append(colour)
    u = OxmlElement("w:u")
    u.set(qn("w:val"), "single")
    props.append(u)
    r.append(props)
    t = OxmlElement("w:t")
    t.text = path
    r.append(t)
    h.append(r)
    p._p.append(h)


original_paragraphs = list(doc.paragraphs)
for prefix, answer, paths in answers:
    matches = [p for p in original_paragraphs if p.text.startswith(prefix)]
    assert len(matches) == 1, prefix
    p = matches[0]
    changed.add(id(p._p))
    p.clear()
    p.add_run(answer + "\nRepository: ").font.color.rgb = purple
    for i, path in enumerate(paths):
        assert Path(path).exists(), path
        if i:
            p.add_run(" ; ").font.color.rgb = purple
        link(p, path)
    p.add_run(
        "\nExecuted validation evidence: TEST-REPORT.md. Start: python scripts/setup.py; docker compose up --build -d."
    ).font.color.rgb = purple
    if prefix.startswith("The complete"):
        section3 = p

for p in original_paragraphs:
    if (
        p.text == "ANSWER (Python reference implementation):"
        or p.text == "ANSWER (FastAPI reference API):"
    ):
        changed.add(id(p._p))
        p.runs[0].text = "ANSWER (Python / FastAPI runnable implementation):"
    if p.text.startswith("Candidate declaration: AI assistance"):
        changed.add(id(p._p))
        p.clear()
        p.add_run(
            "Candidate declaration: AI-assisted tools supported implementation, review, documentation and test generation. The candidate is responsible for reviewing this final revision and understanding/explaining it before submission. Execution evidence describes checks performed during the assisted session; it does not claim the candidate has already independently reviewed every change."
        ).font.color.rgb = purple

unchanged = [canonical(p._p) for p in original_paragraphs if id(p._p) not in changed]
tables = [canonical(t._tbl) for t in doc.tables]
sections = canonical(doc._element.body.sectPr)
# Add the diagrams next to the authorised Section3 answer, preserving original paragraphs.
for label, name in [
    ("Executive architecture — proposed Section3 module", "executive-architecture"),
    ("Full-payment business process — proposed Section3 flow", "full-payment-business"),
]:
    caption = doc.add_paragraph()
    caption.add_run(label).font.color.rgb = purple
    section3._p.addnext(caption._p)
    image = doc.add_paragraph()
    image.add_run().add_picture(
        f"section_03_system_design/diagrams/{name}.png", width=Inches(5.8)
    )
    caption._p.addnext(image._p)
    section3 = image
doc.save(target)
reopened = Document(target)
new_paragraphs = [canonical(p._p) for p in reopened.paragraphs]
assert all(
    p in new_paragraphs for p in unchanged
), "An unauthorised original paragraph changed"
assert tables == [canonical(t._tbl) for t in reopened.tables], "Original table changed"
assert sections == canonical(
    reopened._element.body.sectPr
), "Page/section setup changed"
report = {
    "answer_paragraphs_updated": len(answers),
    "untouched_paragraphs_verified": len(unchanged),
    "original_tables_verified": len(tables),
    "section_page_setup_preserved": True,
    "relative_repository_links": sum(len(a[2]) for a in answers),
    "business_diagrams_embedded": 2,
    "source_backup": str(backup),
    "word_rendering": "Not verified in Microsoft Word; OOXML round-trip and structural checks only.",
}
Path("docs/word-preservation-report.json").write_text(json.dumps(report, indent=2))
print(json.dumps(report, indent=2))
