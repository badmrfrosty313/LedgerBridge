# Codex working agreement for LedgerBridge 2.0

## Product mission
Turn the existing LedgerBridge v0.2.0 into a polished, demonstrable financial-operations automation portfolio product. The core workflow is **import -> validate -> human review -> independently approve -> export -> reconcile**. Demonstrate engineering quality with synthetic, reproducible evidence rather than marketing claims.

## Existing architecture (preserve until a measured reason to change)
- Python 3.11+ application in `ledgerbridge/`, with SQLite persistence, HTTP/WSGI service, and a deterministic document parser.
- Vanilla JavaScript/CSS UI in `ledgerbridge/static/`.
- `unittest` suite in `tests/`, Playwright browser workflow, and cross-platform GitHub Actions in `.github/workflows/test.yml`.
- Demo ERP is **simulated**; do not claim a real ERP/MIP integration.
- Existing README, deployment guide, API docs, security review, pilot kit, and release process are part of the product.

## Scope and branch discipline
- Work in **small, reviewable pull requests** against the `codex/ledgerbridge-v2` integration branch. Do not push directly to `main`, rewrite history, create release tags, or change deployment/visibility without explicit approval.
- Each task begins by inspecting the current code and running the baseline checks where possible.
- Preserve existing user-visible workflows, audit event semantics, role permissions, independent reviewer approval, immutable exports, deduplication, and retry/idempotency guarantees.
- Prefer incremental modules and explicit interfaces over a premature wholesale rewrite to a different framework.
- Implement only the scoped task. Propose scope changes before making them.

## Financial correctness and security
- Represent currency with integer minor units or `Decimal`; never binary floats for financial calculations. Specify rounding and tolerances explicitly and test boundaries.
- Never silently round, infer, auto-correct, or discard mismatched financial data. Expose exceptions for a human reviewer.
- All imported documents are untrusted. Bound input size/row count/complexity; validate types, dates, amounts, and headers; guard against CSV formula injection and unsafe workbook constructs. Do not execute macros or external workbook links.
- No real client/company data, financial documents, credentials, secrets, or personal information in code, fixtures, logs, screenshots, or demos. Use invented data.
- AI extraction, if introduced later, must be opt-in, separate from approval/posting, provider-neutral where practical, and pass deterministic validations.
- Do not connect to or post into real accounting/ERP systems without an authorized, verified contract and a separately approved integration plan.
- Do not weaken local/production mode separation, authentication, CSRF/origin controls, permissions, or audit logging to simplify demo features.

## Definition of done for each Codex task
1. The agreed feature is implemented with tests covering success, rejection, edge cases, regressions, and financial invariants.
2. Relevant commands pass: `python -m unittest discover -s tests -v`, `python -m pilot.run`, `python scripts/release.py --check`; run browser checks when UI changes.
3. Update documentation (README/API/ROADMAP/security considerations as relevant) and include entirely synthetic fixtures.
4. Show exact commands run, test results, changed files, known limitations, and any risks in the PR summary.
5. Provide a manual demo script and objective before/after evidence whenever possible. Never claim an unrun test passed.

## Current priorities
1. Excel .xlsx intake with bounded deterministic mapping/validation and an explicit preview before committing records.
2. Explainable cost-allocation percentage verification and reconciliation, with human-readable exception diagnostics.
3. Configurable simulated accounting export/mapping and round-trip checks. Live third-party integration is out of scope.
4. Portfolio-quality demo, architecture documentation, screenshots, and measurable synthetic case study.
5. Optional OCR/AI-assisted extraction only after deterministic financial controls are solid.

## Authorized full-build campaign

For the owner's one-shot LedgerBridge 2.0 build assignment, the canonical detailed scope and acceptance gates are in [docs/V2_EXECUTION_PLAN.md](docs/V2_EXECUTION_PLAN.md) with milestone Issues #5-#9. Read that document first and finish the in-flight M1 / PR #4 reviews before starting M2. This explicitly authorizes incremental implementation of M2-M6 on a separate campaign branch, subject to the document's test, progress, privacy and no-merge boundaries. The original small-PR preference remains; if Codex cannot use the GitHub API, push milestone commits to a reviewable campaign branch and provide compare URLs. M7 / Issue #10 (OCR and AI) is **design-only until separate owner approval**. Never merge PRs, touch main, create tags/releases or connect real accounting systems as part of this campaign.
