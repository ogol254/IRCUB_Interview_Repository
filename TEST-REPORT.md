# Execution report — IRCUB Sections 1 and 3

Final validation is being recorded from actual command outputs in this session. Entries below are updated after the final dependency/regression run. No generated code is treated as execution evidence.

Working directory: repository root unless explicitly marked frontend. Host: Windows, Python3.13.14, Node22.21.1, Docker29.1.2 with PostgreSQL16/Redis7 Linux containers. Scope excludes Section2.

| Component | Test / command | Expected | Actual | Status |
|---|---|---|---|---|
| Python/database | `python -m pytest -q` (initial validated version) | All tests pass | 46 passed; 1 upstream deprecation warning | PASS |
| Frontend | `npm run build` | TypeScript and production bundle | Build succeeded | PASS |
| Frontend | `npm run lint` | Strict TypeScript checks | No errors; this is not ESLint | PASS |
| Frontend | `npm test` | Component/validation tests | 11 passed, 2 files | PASS |
| Frontend | `npm run e2e` | Real API tablet journey | 1 passed: two lines, receipt, duplicate rejection; PNG/PDF saved | PASS |
| Docker | `docker compose build` (corrected run) | All images built | backend/frontend/mock-fmis built | PASS |
| Docker | `docker compose up -d --wait` | Five healthy services | PostgreSQL, Redis, backend, mock, frontend healthy | PASS |
| API | `python scripts/smoke.py` | Health/OpenAPI/HMAC/idempotency/concurrency/cache/FMIS | 16 live assertions passed | PASS |
| Diagrams | `node scripts/render-diagrams.mjs` | All Mermaid source renders | 8 SVGs generated | PASS |
| Diagrams | `node scripts/diagram-previews.mjs` | Business PNGs for Word | 2 PNGs generated | PASS |
| Dependency audit | npm install/audit after updates | No known npm advisories | Zero advisories reported | PASS |
| Dependency audit | Initial `python -m pip_audit --path .tools/python ...` | Inspect known advisories | Found older Starlette/pytest/Black advisories; updated versions being revalidated | INITIAL FINDINGS — not final |

## Failures encountered and corrected

- Docker engine was stopped and sandbox access denied; started with authorised Docker access.
- Initial .NET attempt was abandoned at the user's instruction to retain Python; no .NET implementation is submitted.
- Python virtualenv initialization was blocked by local permissions. Validation used repository-local `.tools/python` dependency installation with authorised access; containers provide an independently reproducible Linux runtime.
- PostgreSQL localhost/IPv6 connection stalled. Native scripts use127.0.0.1 and bounded connection timeouts; Windows launcher uses selector event loop.
- Initial penalty expectation for2Feb was35 but correct amount was45 because the second payment occurred15Feb. Corrected the test; implementation's as-of cutoff was correct.
- Frontend initially lacked Node TypeScript declarations for E2E files. Added declarations and reran build/type checks/container build successfully.
- npm10 resolver repeatedly crashed while updating Vitest peers. Rebuilt lockfile using npm11.7; checked-in lock supports `npm ci` and successful container builds.
- Initial frontend package versions had5 advisories. Updated Vite/Vitest/Playwright; install reports0.

## Validation limits

No50M-row or5000-payments/min benchmark; no real payment provider, FMIS, SMS/email or identity provider; no HA/PITR/production rollout drill; no full screen-reader/WCAG certification. Section3 acceptance criteria and NFRs are proposals, not executed compliance tests. Word structural/OOXML validation is planned; Microsoft Word pagination/rendering must be reviewed by the candidate. Relative file links can be restricted by Word's security policy.

Unit/integration tests use fresh isolated PostgreSQL databases. Live smoke and E2E add only uniquely named synthetic payments to the demonstration ledger. Generated credentials are excluded from committed files and are not included in this report.
