# Multi-step payment capture — Section 1 Frontend Q1

React19, TypeScript5.8, Vite6.4.3. Lucide icons, restrained agency colours, responsive cards, readable USD figures and ≥46px controls. CSS implements this one form without adding a large component framework. The server determines whether a financial transaction is accepted.

## Start

Requires Node22.21+ and the running backend. From this directory:

```sh
npm ci
npm run dev
```

Open http://localhost:5173. Production: `npm run build`; output is `dist/`. Root Compose builds it and serves through nginx. `VITE_API_URL` defaults `http://localhost:8000`; set it before a development start/build when using a different backend. Vite variables are public: **never put HMAC/provider secrets in them**.

Copy only `OFFICER_API_KEY` from the locally generated root `.env` into the password field. The app holds it in React memory, never localStorage/sessionStorage. Reload starts a new officer connection. The demo has one credential rather than a production login/role-management POC.

## Demonstration

1. Connect, search `TEST-001`, `0700000001` or `WA-001`; select Amina Demo.
2. Select Water supply, continue; add positive USD amount, channel and a unique synthetic external reference. Add a second line and inspect total. Remove/edit lines as needed.
3. Review payer/revenue/lines before confirmation. Server commits each line and returns accepted/rejected results.
4. Print accepted receipt, or start New payment. Try `SEED-1` to demonstrate a server duplicate rejection; rejected lines are never included in the accepted receipt total.

Client validation prevents zero/negative/more-than-two-decimal amounts, blank/long references and duplicates within the form. Server checks payer, revenue activity, global duplicates and financial persistence. Network/503 error retains the exact body/key, disables edits and offers same-request retry because payment may already have committed. Closing/reloading during uncertain submission loses the in-memory request key: supervisor reconciliation is then required before recapture. Persisting a recoverable, identity-bound draft is a future production improvement.

The form captures unallocated payments, consistent with optional assessment_id in the supplied model. Allocation is demonstrated by callback/API tests; there is no fake bill selector or hidden POC registry implementation.

## Tests

```sh
npm run build
npm run lint
npm test
npx playwright install chromium
# Start root Compose first; .env must exist
npm run e2e
```

`lint` currently runs strict TypeScript checks, not ESLint. Component tests mock HTTP to cover search, amounts, multiple lines, receipt, duplicate rejection and server-failure retry identity. The Playwright tablet test uses **real** API, synthetic payer and unique references; saves a screenshot and print PDF under ignored `test-results/`. A browser download and live containers are required. It leaves only synthetic demonstration payments.

Accessibility: labelled fields, keyboard controls, visible focus, alert/status messages, step `aria-current`, selection `aria-pressed`, responsive layout and print styling. Automated tests do not establish full WCAG conformance; screen-reader and contrast review remain production release checks. No claim of a full accessibility certification is made.

Troubleshooting:401 means wrong officer credential; API/network errors require backend health and matching CORS origin; duplicate reference is a stored financial rejection, not a network error. Port5173 is used by both Vite and Compose, so run one frontend at a time. Node/npm resolver errors can be avoided with the checked-in lockfile and `npm ci`; npm11.7 was used to regenerate the lockfile after an npm10 resolver bug.
