# LedgerBridge 2.0 campaign status

Branch: `codex/ledgerbridge-v2-campaign`

## Latest pushed checkpoint

`a2cb6f0` — addresses the independent Issue #8 review: removes Auth's schema-version write; backs up all existing document databases below schema v6 before migration; makes mapped export confirmation admin-only and independent from the mapping editor; checks current target batch and receipt identity during reconciliation; and rejects XLSX source labels that cannot fit their row-provenance suffix before issuing a preview token. The local full test suite, pilots, release check, and browser journey pass. GitHub Actions validation is pending for this pushed checkpoint.

## Independent review read

The newest Issue #8 review comment is [6131836536](https://github.com/badmrfrosty313/LedgerBridge/issues/8#issuecomment-6131836536), reviewing `1bf035f`. It identified an Auth schema-version downgrade, inconsistent mapped-export authorization, receipt identity gaps, backup coverage for versioned legacy databases, and a maximum-length XLSX filename confirmation failure. The `a2cb6f0` checkpoint includes code and regression coverage for all five.

## Local verification at this working checkpoint

- `python -m unittest discover -s tests -q`: 79 tests passed.
- `python -m pilot.run`: passed; 11 synthetic imports, 8 approved/exported, 3 rejected, exact total `$638.00`, backup restore.
- `python -m pilot.campaign_demo`: passed end-to-end; synthetic XLSX source, 10,001 cents allocated/mapped/exported/received, 0-cent difference, retry replayed. One observed run took 29.213 ms; this is a local sample, not a performance or savings claim.
- `python scripts/release.py --check`: passed after preserving the v0.2.0 metadata heading.
- Compileall, JavaScript syntax, `pip check`, and `git diff --check`: passed. Production Waitress startup/health passed from `/tmp/ledgerbridge-prod-deps` with a temporary synthetic database.
- Full Playwright browser workflow passed locally with fresh temporary SQLite files, isolated ports, and system Chromium. It covers XLSX preview/formula rejection/confirmation; allocation preview/save/refresh/independent reviewer approval, invalid totals and duplicate destinations; mapped export by an independent administrator; mapping dry-run including an explicitly enabled negative credit; round-trip cents; simulated ERP retry; immutable export lock; queue filters; keyboard, empty state, HTML safety, desktop and mobile layout. Playwright Chromium is available under `/tmp/ledgerbridge-playwright-browsers`.

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
