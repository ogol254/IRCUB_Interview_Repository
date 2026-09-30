# Five actor journeys

See [business diagram](diagrams/actor-journeys.svg) / [Mermaid source](diagrams/actor-journeys.mmd).

| Actor | Journey | Exception |
|---|---|---|
| Payer | Receive notice → open secure link → review debt → pay/request plan → receive confirmation → eligible enforcement stops | Expired link needs verified reissue; declined payment leaves debt visible |
| Compliance officer | Open assigned cases → inspect notices/balance → contact payer → record action/propose plan → follow up → resolve | Missing evidence enters review; no direct balance edits |
| Auditor | Open escalation → inspect policy/delivery → review decisions/allocations → export findings | Missing evidence flagged; read-only privileges enforced |
| Administrator | Review approved policy → validate new rules → set effective date → publish version → monitor | Invalid ordering rejected; existing notices retain their original version |
| Water field officer | Receive assignment → check current eligibility → visit → record evidence → close valid order | Cancelled/stale order stops action; offline completion stays pending |
