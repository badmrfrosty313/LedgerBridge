# LedgerBridge 2.0 campaign status

Branch: `codex/ledgerbridge-v2-campaign`

## Current checkpoint

The current working checkpoint extends the allocation review and integrity work with a transactionally versioned SQLite migration path, shared allocation validation for templates and previews, optimistic template revisions, authorized template endpoints, a structured reviewer editor, and additional allocation/XLSX tests. The changes are not yet pushed or declared an M2 completion.

## Evidence at this checkpoint

- `python -m unittest discover -s tests -v`: 52 tests passed, including old-database backup preservation and allocation migration tests.
- `python -m pilot.run`: passed; 11 synthetic records, 8 exported, `$638.00`.
- `python scripts/release.py --check`: passed (`v0.2.0` metadata).
- `python -m compileall -q ledgerbridge`, `node --check ledgerbridge/static/app.js`, `node --check tests/browser-check.cjs`, and `git diff --check`: passed before the last status edit.
- Playwright workflow: added true synthetic XLSX and allocation/template workflow coverage, but not executed locally because Chromium download redirected to `storage.googleapis.com` and the current environment returned `403 Domain forbidden`. The onboarding network draft now includes that host and `cdn.playwright.dev`; the saved change requires user review/publication. Browser status remains unverified pending GitHub Actions.

## Remaining work

- Finish review/acceptance of M2, including a completed Playwright run and any issues found there. The legacy CSV intentionally remains one row per source document and does not contain split allocation rows.
- Complete the remaining M1 XLSX CI gate; single-sheet XLSX support is the current documented behavior.
- Implement M3 simulated mapping profiles, dry-run, immutable mapped exports, delivery/reconciliation.
- Then implement M4 reviewer dashboard, M5 security/reliability regression gates, and M6 synthetic portfolio/release-candidate artifacts. M7 remains excluded.

Continuation: run the full checks, push this checkpoint, verify the actual browser CI status, fix failures, then resume the next unmet M2 criterion before starting M3.
