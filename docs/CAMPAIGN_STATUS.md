# LedgerBridge 2.0 campaign status

Branch: `codex/ledgerbridge-v2-campaign`

## Current checkpoint

Commit `e2e618d` is pushed on `codex/ledgerbridge-v2-campaign`. The current working checkpoint adds a versioned mapping profile, a read-only dry-run, profile/source-digest stale checks, optional allocation expansion, immutable mapped snapshots, and reviewer-separate confirmation. M3 is not complete until the new CI run and its browser gate pass.

## Evidence at this checkpoint

- `python -m unittest discover -s tests -v`: 57 tests passed, including M2 financial integrity, migrations, permissions, M3 mapping dry-runs, stale confirmation, and simulated receipt retry.
- `python -m pilot.run`: passed; 11 synthetic records, 8 exported, `$638.00`.
- `python scripts/release.py --check`: passed (`v0.2.0` metadata).
- `python -m compileall -q ledgerbridge`, `node --check ledgerbridge/static/app.js`, `node --check tests/browser-check.cjs`, and `git diff --check`: passed before the last status edit.
- GitHub Actions run 44 for `e2e618d`: all four Python matrix jobs passed; the browser job failed at `Verify browser workflow` (exit code 1). The public run page does not expose its assertion output. Local reproduction found and fixed a strict locator collision and an async selection race; the complete browser journey now passes locally using system Chromium 154 with `PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH=/usr/bin/chromium`. The managed browser installer still redirects to `storage.googleapis.com` and is blocked; the onboarding draft now allows that host and `cdn.playwright.dev`, but requires user review/publication. A new CI run for the corrected checkpoint is still required.

## Remaining work

- Finish review/acceptance of M2 and M1 by verifying the next CI run is green. The legacy CSV intentionally remains one row per source document and does not contain split allocation rows.
- Finish M3 with the next browser CI gate, review remaining mapping edge cases, and report the fake ERP boundary accurately.
- Then implement M4 reviewer dashboard, M5 security/reliability regression gates, and M6 synthetic portfolio/release-candidate artifacts. M7 remains excluded.

Continuation: push this corrected checkpoint, verify its actual Python matrix and Playwright status, fix any failures, complete M2/M1 acceptance, then finish M3 before moving to M4.
