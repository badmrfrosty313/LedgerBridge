# LedgerBridge 2.0 campaign status

Branch: `codex/ledgerbridge-v2-campaign`

## Latest pushed checkpoint

`3bec278` — prevents reselecting the active document from asynchronously rebuilding its form, a race exposed by CI's browser failure annotation; the browser helper now waits for a newly selected row before editing. GitHub Actions run [38298874976](https://github.com/badmrfrosty313/LedgerBridge/actions/runs/38298874976) passed the complete matrix, browser journey, and production startup check for this checkpoint.

## Issue #5 review read

The latest public Issue #5 architecture review comment is [6130205816](https://github.com/badmrfrosty313/LedgerBridge/issues/5#issuecomment-6130205816), reviewing `197c9df` and `33c6667`. It called out template input validation, missing template role/CSRF and revision coverage, the missing corrupt-after-approval export regression, legacy schema migration/backup verification, and M1/M2-specific Playwright coverage. These areas now have implementation and automated tests across the prior campaign commits and current additions; M2 is not declared complete until final CI is green.

## Local verification at this working checkpoint

- `python -m unittest discover -s tests -q`: 75 tests passed.
- `python -m pilot.run`: passed; 11 synthetic imports, 8 approved/exported, 3 rejected, exact total `$638.00`, backup restore.
- `python -m pilot.campaign_demo`: passed end-to-end; synthetic XLSX source, 10,001 cents allocated/mapped/exported/received, 0-cent difference, retry replayed. One observed run took 23.474 ms; this is a local sample, not a performance or savings claim.
- `python scripts/release.py --check`: passed after preserving the v0.2.0 metadata heading.
- Compileall, JavaScript syntax, `pip check`, and `git diff --check`: passed. Production Waitress startup/health passed from `/tmp/ledgerbridge-prod-deps` with a temporary synthetic database.
- Full Playwright browser workflow passed locally on both system Chromium and Playwright-pinned Chromium 151 after the row-selection fix, with fresh temporary SQLite files and isolated ports. It covers XLSX preview/formula rejection/confirmation; allocation preview/save/refresh/independent approval, invalid totals and duplicate destinations; mapping dry-run/confirmation including an explicitly enabled negative credit; round-trip cents; simulated ERP retry; immutable export lock; queue filters; keyboard, empty state, HTML safety, desktop and mobile layout. Playwright Chromium was installed to `/tmp/ledgerbridge-playwright-browsers` because the managed home cache is not writable.

## Remote CI and remaining acceptance gates

Actions runs [38297176502](https://github.com/badmrfrosty313/LedgerBridge/actions/runs/38297176502), [38297301924](https://github.com/badmrfrosty313/LedgerBridge/actions/runs/38297301924), [38297977618](https://github.com/badmrfrosty313/LedgerBridge/actions/runs/38297977618), [38298253269](https://github.com/badmrfrosty313/LedgerBridge/actions/runs/38298253269), and [38298593182](https://github.com/badmrfrosty313/LedgerBridge/actions/runs/38298593182) failed browser CI while the Python matrix passed. Run `38298593182` exposed the row-selection race. It is fixed and run [38298874976](https://github.com/badmrfrosty313/LedgerBridge/actions/runs/38298874976) passed all CI jobs, including the cross-platform Python matrix, Playwright browser workflow, and production Waitress startup. A docs-only checkpoint will rerun the same gate.

### Milestone state

- M1/M2: implementation includes session-owned one-use XLSX previews, browser confirmation tests, allocation templates, versioned migrations, independent approval, total-change review-required state, corrupted persisted allocation checks on approval/export, and concurrency tests. Legacy CSV remains intentionally one row per source document. Final CI/browser green gate remains.
- M3: versioned generic account mapping, non-persistent dry-run, immutable allocation-aware mapped export, mock ERP idempotency, and reconciliation logic are implemented. No live connector.
- M4: reviewer queue search/filter/status summaries, exception/source/history guidance, keyboard and responsive checks, and a visible source→export→simulated receipt cent reconciliation panel are implemented.
- M5: tests now cover malformed/corrupted persisted records, XLSX path/external-link/compression limits, malformed Base64, concurrency, legacy backup/restore, and fail-closed newer DB versions. Cross-platform remote matrix and final CI remain.
- M6: a synthetic end-to-end harness, candidate guide, manual demo, architecture/sequence diagrams, benchmark caveat, screenshot plan, accessibility notes, and no-merge/release checklist are added. Final CI and final artifact review remain.
- M7 OCR/AI is excluded.

Continuation: commit and push the current checkpoint, verify the complete GitHub Actions matrix/browser result, fix any failures, then continue closing any remaining M1–M6 acceptance gaps without merging or publishing.
