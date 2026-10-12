# LedgerBridge 2.0 campaign status

Branch: `codex/ledgerbridge-v2-campaign`

## Latest pushed checkpoint

`53c271e` — M4 reconciliation UX, M5 trust/regression coverage, and M6 synthetic candidate evidence. A follow-up CI change adds the campaign harness to the Python matrix.

## Issue #5 review read

The latest public Issue #5 architecture review comment is [6130205816](https://github.com/badmrfrosty313/LedgerBridge/issues/5#issuecomment-6130205816), reviewing `197c9df` and `33c6667`. It called out template input validation, missing template role/CSRF and revision coverage, the missing corrupt-after-approval export regression, legacy schema migration/backup verification, and M1/M2-specific Playwright coverage. These areas now have implementation and automated tests across the prior campaign commits and current additions; M2 is not declared complete until final CI is green.

## Local verification at this working checkpoint

- `python -m unittest discover -s tests -v`: 68 tests passed.
- `python -m pilot.run`: passed; 11 synthetic imports, 8 approved/exported, 3 rejected, exact total `$638.00`, backup restore.
- `python -m pilot.campaign_demo`: passed end-to-end; synthetic XLSX source, 10,001 cents allocated/mapped/exported/received, 0-cent difference, retry replayed. One observed run took 20.952 ms; this is a local sample, not a performance or savings claim.
- `python scripts/release.py --check`: passed after preserving the v0.2.0 metadata heading.
- Compileall, JavaScript syntax, and `git diff --check`: passed.
- Full Playwright browser workflow passed locally using installed system Chromium at `/usr/bin/chromium`, fresh temporary SQLite files, and isolated ports. It covered XLSX preview/formula rejection/confirm; allocation preview/save/refresh/independent approval; mapping dry-run/confirmation; round-trip cents; simulated ERP retry; immutable export lock; keyboard, empty state, HTML safety, desktop and mobile layout. The managed Playwright browser installer remains restricted by network policy until the saved environment draft is reviewed/published.

## Remote CI and remaining acceptance gates

Actions run [38295323262](https://github.com/badmrfrosty313/LedgerBridge/actions/runs/38295323262) was queued when inspected for checkpoint `53c271e`; no green result is claimed. The prior run for `b37c208` failed its browser workflow after earlier Python jobs passed. The public page does not expose its detailed private job log here. Local replay found and fixed a hard-coded test origin and request-context cookie issue; the corrected complete local browser flow passes. The next pushed commit must be checked in GitHub Actions. Do not call M1–M6 complete while final CI is red or pending.

### Milestone state

- M1/M2: implementation includes session-owned one-use XLSX previews, browser confirmation tests, allocation templates, versioned migrations, independent approval, total-change review-required state, corrupted persisted allocation checks on approval/export, and concurrency tests. Legacy CSV remains intentionally one row per source document. Final CI/browser green gate remains.
- M3: versioned generic account mapping, non-persistent dry-run, immutable allocation-aware mapped export, mock ERP idempotency, and reconciliation logic are implemented. No live connector.
- M4: reviewer queue search/filter/status summaries, exception/source/history guidance, keyboard and responsive checks, and a visible source→export→simulated receipt cent reconciliation panel are implemented.
- M5: tests now cover malformed/corrupted persisted records, XLSX path/external-link/compression limits, malformed Base64, concurrency, legacy backup/restore, and fail-closed newer DB versions. Cross-platform remote matrix and final CI remain.
- M6: a synthetic end-to-end harness, candidate guide, manual demo, architecture/sequence diagrams, benchmark caveat, screenshot plan, accessibility notes, and no-merge/release checklist are added. Final CI and final artifact review remain.
- M7 OCR/AI is excluded.

Continuation: commit and push the current checkpoint, verify the complete GitHub Actions matrix/browser result, fix any failures, then continue closing any remaining M1–M6 acceptance gaps without merging or publishing.
