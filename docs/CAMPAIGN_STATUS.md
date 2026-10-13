# LedgerBridge 2.0 campaign status

Branch: `codex/ledgerbridge-v2-campaign`

## Latest pushed checkpoint

`d2b3223` — records the completed independent Issue #8 review fixes from `a2cb6f0` and `ae8ce1f`. GitHub Actions run [38440269131](https://github.com/badmrfrosty313/LedgerBridge/actions/runs/38440269131) passed the Python matrix, Playwright workflow, release checks, and production startup. The local full test suite, pilots, release check, and Playwright browser journey also pass.

## Independent review read

The newest Issue #8 review comment is [6131836536](https://github.com/badmrfrosty313/LedgerBridge/issues/8#issuecomment-6131836536), reviewing `1bf035f`. It identified an Auth schema-version downgrade, inconsistent mapped-export authorization, receipt identity gaps, backup coverage for versioned legacy databases, and a maximum-length XLSX filename confirmation failure. Checkpoints `a2cb6f0` and `ae8ce1f` include code and regression coverage for all five findings.

## Local verification at this working checkpoint

- `python -m unittest discover -s tests -q`: 79 tests passed.
- `python -m pilot.run`: passed; 11 synthetic imports, 8 approved/exported, 3 rejected, exact total `$638.00`, backup restore.
- `python -m pilot.campaign_demo`: passed end-to-end; synthetic XLSX source, 10,001 cents allocated/mapped/exported/received, 0-cent difference, retry replayed. One observed run took 29.213 ms; this is a local sample, not a performance or savings claim.
- `python scripts/release.py --check`: passed after preserving the v0.2.0 metadata heading.
- Compileall, JavaScript syntax, `pip check`, and `git diff --check`: passed. Production Waitress startup/health passed from `/tmp/ledgerbridge-prod-deps` with a temporary synthetic database.
- Full Playwright browser workflow passed locally with fresh temporary SQLite files, isolated ports, and system Chromium. It covers XLSX preview/formula rejection/confirmation; allocation preview/save/refresh/independent reviewer approval, invalid totals and duplicate destinations; mapped export by an independent administrator; mapping dry-run including an explicitly enabled negative credit; round-trip cents; simulated ERP retry; immutable export lock; queue filters; keyboard, empty state, HTML safety, desktop and mobile layout. Playwright Chromium is available under `/tmp/ledgerbridge-playwright-browsers`.

## Remote CI and remaining acceptance gates

Earlier browser CI failures were traced and fixed; runs [38298874976](https://github.com/badmrfrosty313/LedgerBridge/actions/runs/38298874976), [38440024857](https://github.com/badmrfrosty313/LedgerBridge/actions/runs/38440024857), [38440095000](https://github.com/badmrfrosty313/LedgerBridge/actions/runs/38440095000), [38440226007](https://github.com/badmrfrosty313/LedgerBridge/actions/runs/38440226007), and [38440269131](https://github.com/badmrfrosty313/LedgerBridge/actions/runs/38440269131) passed the complete workflow, including cross-platform Python, Playwright browser, release, and production-startup checks.

### Milestone state

- M1/M2: implementation includes session-owned one-use XLSX previews, browser confirmation tests, allocation templates, versioned migrations, independent approval, total-change review-required state, corrupted persisted allocation checks on approval/export, and concurrency tests. Legacy CSV remains intentionally one row per source document. The Issue #8 review-fix CI gate is green; broader campaign acceptance should still be checked against the master plan before calling M2 complete.
- M3: versioned generic account mapping, non-persistent dry-run, immutable allocation-aware mapped export, mock ERP idempotency, and reconciliation logic are implemented. No live connector.
- M4: reviewer queue search/filter/status summaries, exception/source/history guidance, keyboard and responsive checks, and a visible source→export→simulated receipt cent reconciliation panel are implemented.
- M5: tests now cover malformed/corrupted persisted records, XLSX path/external-link/compression limits, malformed Base64, concurrency, legacy backup/restore, and fail-closed newer DB versions. These CI checks pass for this checkpoint; campaign-wide final review remains.
- M6: a synthetic end-to-end harness, candidate guide, manual demo, architecture/sequence diagrams, benchmark caveat, screenshot plan, accessibility notes, and no-merge/release checklist are added. Final CI and final artifact review remain.
- M7 OCR/AI is excluded.

Continuation: commit and push the current checkpoint, verify the complete GitHub Actions matrix/browser result, fix any failures, then continue closing any remaining M1–M6 acceptance gaps without merging or publishing.
