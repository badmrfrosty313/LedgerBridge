# LedgerBridge 2.0: Full execution plan for Codex

**Status:** engineering plan, NOT a list of shipped features. **Owner approval is required for merges, releases, public deployment, external services, and real financial connections.**
**Last planned:** 2026-10-12.
**Integration branch:** codex/ledgerbridge-v2.
**Initial feature:** Issue #3, draft PR #4 on codex/excel-preview-complete. Codex may have to finish it before starting the campaign.

## North star

Deliver a compelling, truthful **single-organization** financial operations automation portfolio product that demonstrates:

1. Ingest structured text, CSV, and defensive XLSX via **preview before persistence**.
2. Validate inputs with precise exceptions rather than guessed or silently rounded data.
3. Review invoice documents, split costs by synthetic funds/departments using exact percentages and integer cents.
4. Enforce **independent human approval**, audit changes, and lock exported snapshots.
5. Map approved amounts to a generic simulated accounting import format with a **dry-run**, immutable export, mock ERP receipt and reconciliation.
6. Provide an intuitive, accessible demo, robust tests and reproducible synthetic evidence of time/actions and accuracy.

The product should be credible to a software engineer, accounting-operations hiring manager, and a reviewer with no prior knowledge of the repo. The existing Python + SQLite + vanilla JS implementation is the foundation, **not scaffolding to throw out**.

**Do NOT** claim production MIP/Paycor integration, real customer pilots, SOC 2/HIPAA compliance, AI-powered extraction where none exists, or live financial posting.

## Starting point / anti-collision rule

- The baseline v0.2.0 has text and CSV intake, rule exceptions, deduplication, reviewer/admin roles, independently approved records, immutable CSV exports, audit events, a local mock ERP with idempotent delivery, and a synthetic pilot. Preserve these as regression requirements.
- Issue #3 / PR #4 is the Excel preview feature. Do not create a duplicate implementation. **Finish its known review items first**: blank required fields must be row errors; session ownership must be checked BEFORE consuming a token; stale browser confirmation must be cleared on subsequent failed uploads; add security/edge and true XLSX Playwright coverage. Reconcile any discrepancy in issue acceptance around single-sheet support explicitly and document the limitation.
- If a Codex session is already running on PR #4, do not race it by writing simultaneously to the same branch. First wait for its completion and use the latest pushed head.
- This plan may live on codex/ledgerbridge-v2 while PR #4's head branched before it was committed. **Read this file from the integration branch explicitly** when starting the full campaign; do not assume it exists in an older checkout.
- Codex may access GitHub through git while GitHub REST requests are blocked. Commit and push to named branches; report compare links when PR creation is unavailable. Do not pretend a PR exists if it does not.

## Non-negotiable engineering contracts

### Correct money and allocations
- Every persisted document amount, allocation output, export amount and reconciliation sum uses integer cents (or Decimal at conversion boundaries). Never perform financial calculations using JS/Python binary floating point.
- Percentage input is a decimal **string** with at most four fractional digits, or a stricter clearly documented precision. Reject negative, NaN, infinite, overly precise and greater-than-100 percentages. The signed document total may be negative for supported credit flows, subject to existing review rules.
- A completed allocation must total exactly 100.0000% and allocate exactly the source amount in cents. Use a stable deterministic remainder policy (e.g., floor positive absolute minor units and distribute leftover cents by descending fractional remainder, then lexically stable destination key; reapply original sign for negative totals). Display residuals explicitly. Never mutate the source invoice total to make the splits balance.
- A business-rule error (unknown account, approval limit, reconciliation mismatch, missing required fields) must not become an auto-fix or auto-approval. A rejected batch must have no partial unintended writes.
- If allocation/mapping/config changes after approval, approvals must be revalidated or invalidated according to documented rules, with auditable versioning. Changing an exported record is forbidden.

### Security/privacy and permissions
- All inbound files and user strings are untrusted. Protect against ZIP bombs, malicious workbook structure, formulas/external relationships, HTML/CSV formula injection, path tricks, excessive memory/time use, broken UTF-8, and malformed requests with bounded limits.
- Preview/dry-run never persists source records or makes external network calls. Confirmation is explicitly user-triggered, one-use/expiring and tied to server-owned identity and session; separate actors cannot consume each other's previews.
- Keep role-based server authorization, CSRF/host/origin protections, session expiry, audit attribution and two-human control. A browser disabling controls is NOT sufficient authorization.
- Any public repo test data, screenshots, logs, docs and benchmark data must be **entirely invented**. No real company invoices, actual employee names, personal details, secrets, tokens, spreadsheets, payroll/ERP records or third-party confidential specifications.
- No live MIP/ERP, banking, payroll or payment integrations. No public hosting changes or traffic to third-party APIs without distinct user approval.

### Architecture and review
- Preserve SQLite and Python HTTP/WSGI backend and vanilla JS UI unless an approved, measured design proves a framework migration is necessary.
- Introduce small coherent modules, migrations, DTOs/API endpoints and tests. Make state ownership explicit, especially for allocation and export operations; use DB transactions/optimistic revisions.
- Use small reviewable milestone commits; maintain docs and a status/checklist in the campaign branch. Do not rewrite git history, touch main, merge PRs, tag releases, disable failing tests or auto-release.
- Keep the original 11-case pilot exactly reproducible: 8 approved records totaling **$638.00**. Do not corrupt this fixture to make new tests pass.

## Sequential implementation milestones

### M1: Excel intake acceptance gate
**Issue #3:** https://github.com/badmrfrosty313/LedgerBridge/issues/3
**Draft PR #4:** https://github.com/badmrfrosty313/LedgerBridge/pull/4

First finish all outstanding review points and required automated tests, especially browser XLSX workflow and token correctness. Validate that upload preview causes no persistence, confirm imports only drafts, malformed worksheets are safe, and roles/approval remain correct. All matrix CI green before declaring M1 ready. Never merge PR #4 automatically.

### M2: Allocation engine and reviewer controls
**Issue #5:** https://github.com/badmrfrosty313/LedgerBridge/issues/5

Design a versioned, auditable set of allocations per document; target keys use invented fund/department/account IDs. Support a small reusable template library. Show **source total, input percentages, computed cent shares, total allocated and difference**, before saving. Require 100%, deterministic remainder and complete cents reconciliation (including 1-cent and negative totals). Surface validation errors, not guesses. Follow permissions and independent approval. If the source is already exported, its snapshot must remain immutable. A total of exactly one cent split across multiple recipients must not disappear or become two cents. Test every corner case in Issue #5, including safe migrations of existing SQLite files.

### M3: Generic simulated accounting mapping and dry-run
**Issue #6:** https://github.com/badmrfrosty313/LedgerBridge/issues/6

Define a versioned mapping profile from documents or split allocations to an invented accounting import schema. Provide an admin-reviewed **dry-run** listing mapped rows, rejected/unmapped rows, source IDs and signed cent totals, without writing to exports or mock ERP. Require explicit confirmation to produce an immutable snapshot with mapping version and source provenance, then preserve exactly-once effects with the existing simulated ERP idempotent receipt contract. Reconcile source totals -> allocation shares -> export batch -> mock-received batch, with actionable discrepancies. Keep the existing default CSV export behavior compatible or provide a tested nonbreaking migration. Never call it a live MIP connector.

### M4: Review and reconciliation experience
**Issue #7:** https://github.com/badmrfrosty313/LedgerBridge/issues/7

Make exception and approval workflows easy to understand: search and filters, full precision, imported source and edit history, allocation preview/provenance, mapping failures, explicit approval roles and reconciliation view. Test keyboard navigation, empty/error states, 1280px and mobile layout, HTML safety, and a complete Playwright synthetic reviewer journey. A demo reset, if implemented, applies ONLY in explicit loopback demo mode. Do not bypass auth to simplify screenshots.

### M5: Trust and regression gate
**Issue #8:** https://github.com/badmrfrosty313/LedgerBridge/issues/8

Exercise attacks and edge cases across file imports, mapping, permissions, concurrency, stale revisions and exports. Verify schema versioning, backup and restore compatibility from v0.2.0 and controlled SQLite migrations. Ensure bounded memory/CPU for max allowed files and 500 rows and run all supported platforms. Review all public artifacts for invented-only data. Update security review with specific verified controls and honest residual risks. No compliance claims.

### M6: Portfolio-ready release candidate
**Issue #9:** https://github.com/badmrfrosty313/LedgerBridge/issues/9

Deliver an end-to-end synthetic harness:
  XLSX -> row preview -> draft -> allocation split -> different approver -> mapping dry-run -> immutable export -> simulated ERP receipt -> reconciliation.
Add easy quickstart, architecture and sequence diagram, API/developer documentation, screenshot plan using ONLY synthetic data, accessibility notes, a two-minute demo, a security/tradeoffs section, and a clearly labeled reproducible **synthetic** benchmark. Measure elapsed durations and human actions where actually observed; do not invent real operational savings.

Refresh README and release notes to describe shipped behavior, not planned behavior. Provide v2.0 **candidate** packaging and a merge/release checklist. No release tags, deployment, automatic merge or changes to main.

### M7: Explicitly gated stretch, NOT authorized to implement
**Issue #10:** https://github.com/badmrfrosty313/LedgerBridge/issues/10

OCR/AI assistance is a design-only backlog unless the owner separately approves added dependencies, compute, API costs, external transmission/privacy and integration risk. Do not implement it or buy anything as part of the autonomous campaign. A future OCR/AI proposal must preserve human approval and deterministic financial validation.

## Acceptance matrix: every milestone

Run (exact environment-specific command as appropriate):
- python -m unittest discover -s tests -v
- python -m pilot.run
- python scripts/release.py --check
- python -m compileall -q ledgerbridge
- node --check ledgerbridge/static/app.js
- npm run test:browser with the authenticated test server and mock ERP started as in GitHub Actions; Chromium absence in Codex is an environment restriction, **not** a passed test.
- GitHub Actions: Python 3.11 + 3.12 on Windows and Ubuntu, plus actual Playwright workflow. Verify completed statuses, never claim an in-progress job passed.
- Milestone-specific negative tests, two-person approval, data-privacy check and release dry-run.
- Before/after totals and signed-cent invariants must have explicit assertions. 0 unexplained balance differences. Document any expected differences as blocking review issues.

Each stage is DONE only when its criteria/tests and documentation are complete. If an environment cannot perform a check, report it as *unverified* and point to alternative verified CI evidence. Green existing browser tests do not substitute for new feature-specific Playwright tests.

## Working mode for one long Codex assignment

The user authorizes Codex to implement **M1 acceptance fixes and M2-M6**, sequentially and autonomously within this written scope. Codex should **not** stop after drafting a plan or completing just the first coding milestone when more approved work remains and time/context allow. Do not ask the owner to approve routine naming, files or UI decisions; choose conservative approaches and explain tradeoffs.

- First inspect latest remote refs and read AGENTS.md, this execution plan and milestone issues or their full descriptions in this file.
- Complete M1 on the existing PR #4 branch ONLY if no other Codex session is concurrently updating it; otherwise wait and begin after its latest head is available.
- Create a clearly named separate **campaign feature branch** from the latest M1 feature head for M2-M6. Bring this plan into that branch from the integration branch as needed. Do not branch from older main or overwrite M1 work. Do not alter the existing PR #4 head after taking a campaign branch unless making explicit review fixes.
- Commit after each milestone, with specific test evidence and a STATUS section in the campaign branch. Push checkpoints if safe. If GitHub API cannot create PRs, output comparison URLs rather than claiming they exist.
- Where feasible, make separate coherent feature branches/stacked reviewable PRs per milestone; if this would prevent autonomous progress because GitHub API is blocked, maintain an orderly single campaign branch **with one checkpoint commit per milestone**, never one opaque thousand-file diff.
- Continue from M2 through M6 unless blocked by an unsafe migration, missing business decision that could materially change financial meaning, external cost/permission, irreconcilable tests, or exhausted session budget. On interruption, finish with exact next step and commit so the next Codex session can resume without repeating work.
- Do NOT merge pull requests automatically, create tags or releases, change repo visibility/settings, write production data, enable paid services, or touch real financial systems.

### Required progress report at each checkpoint
1. Milestone, commit SHA and precise branch.
2. What changed and what intentionally did not.
3. Test command and **observed** results; CI links and completed status.
4. Known risks/blockers, and next uncompleted acceptance criterion.
5. Compare URL or PR URL if genuinely available.
6. Exact one-line continuation instruction to the next Codex session.

## What is NOT required to call v2.0 successful

No live ERP integration, multi-tenancy, SSO, external OCR/AI, hosted SaaS, payroll access, bank connectivity, machine-learning benchmark claims, real-world business pilot, or bespoke frontend framework. A correct, demonstrable local-first portfolio product is the finish line.
