# Section 3 — Revenue Compliance & Enforcement design

This is the written system-design exercise. No compliance/enforcement engine or Section2 POC is implemented. Section1 supplies executable payment/billing evidence; it is not a claim that the proposed compliance module exists.

Read [scope/assumptions](assumptions-and-scope.md), [FR-001–023](functional-requirements.md), [measurable proposed NFRs](non-functional-requirements.md), [data model](data-model.md), [architecture](architecture.md), [four stories](user-stories.md), [six flows](end-to-end-flows.md) and [five journeys](user-journeys.md).

Diagrams have editable Mermaid sources and standalone SVGs:

| Audience / purpose | Readable export | Source |
|---|---|---|
| Ministry executive architecture | [SVG](diagrams/executive-architecture.svg) | [Mermaid](diagrams/executive-architecture.mmd) |
| Technical trust boundaries | [SVG](diagrams/technical-architecture.svg) | [Mermaid](diagrams/technical-architecture.mmd) |
| Business debt/case model | [SVG](diagrams/business-model.svg) | [Mermaid](diagrams/business-model.mmd) |
| Technical relationships | [SVG](diagrams/technical-erd.svg) | [Mermaid](diagrams/technical-erd.mmd) |
| Six business flows | [SVG](diagrams/business-flows.svg) | [Mermaid](diagrams/business-flows.mmd) |
| Full mobile-money payment process | [SVG](diagrams/full-payment-business.svg) | [Mermaid](diagrams/full-payment-business.mmd) |
| Payment/cancellation/FMIS sequence | [SVG](diagrams/full-payment-sequence.svg) | [Mermaid](diagrams/full-payment-sequence.mmd) |
| Five actor journeys | [SVG](diagrams/actor-journeys.svg) | [Mermaid](diagrams/actor-journeys.mmd) |

Business architecture and full-payment PNGs are embedded in Word. Re-render from root with `node scripts/render-diagrams.mjs` and `node scripts/diagram-previews.mjs`; the latter uses the frontend Playwright browser. All operational targets/defaults beyond the assessment require agency sign-off.
