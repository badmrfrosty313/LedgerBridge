# LedgerBridge 2.0 campaign status

Branch: `codex/ledgerbridge-v2-campaign`

## Current checkpoint

Commit `e2f4e0e` is pushed on `codex/ledgerbridge-v2-campaign`. Current uncommitted M4 work broadens queue search, explains reviewer/immutable-export controls, and tests empty states, keyboard selection, inert HTML-looking content, and 1280px/mobile layout.

## Evidence at this checkpoint

- `python -m unittest discover -s tests -v`: 57 tests passed, including M2 financial integrity, migrations, permissions, M3 mapping dry-runs, stale confirmation, and simulated receipt retry.
- `python -m pilot.run`: passed; 11 synthetic records, 8 exported, `$638.00`.
- `python scripts/release.py --check`: passed (`v0.2.0` metadata).
- `python -m compileall -q ledgerbridge`, `node --check ledgerbridge/static/app.js`, `node --check tests/browser-check.cjs`, and `git diff --check`: passed before the last status edit.
- GitHub Actions run 44 for `e2e618d`: all four Python matrix jobs passed; the browser job failed at `Verify browser workflow`. Run 45 for `e2f4e0e` again passed the four-job Python matrix but failed its browser job. GitHub's public run page exposes only the failed step, not its Playwright assertion. Local replay found a race where the test edited mapping controls before the profile load finished; the browser test now waits for that load. The full browser journey—including M1, allocation, mapping, and M4 interaction coverage—passes locally using system Chromium 154 with `PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH=/usr/bin/chromium`. The managed browser installer still redirects to `storage.googleapis.com` and is blocked; the onboarding draft allows that host and `cdn.playwright.dev`, but requires user review/publication.

## Remaining work

- Finish review/acceptance of M2 and M1 by verifying the next CI run is green. The legacy CSV intentionally remains one row per source document and does not contain split allocation rows.
- Finish M3 with the next browser CI gate and review remaining mapping edge cases. The configured connector is strictly local/simulated.
- Finish M4 accessibility, dashboard and reconciliation acceptance. Current work covers filters, reviewer guidance, 1280px/mobile overflow, keyboard queue selection, empty filtering, and inert HTML-like values; broader workflow acceptance still remains.
- Then implement M4 reviewer dashboard, M5 security/reliability regression gates, and M6 synthetic portfolio/release-candidate artifacts. M7 remains excluded.

Continuation: push the M4 checkpoint, verify the next CI run's Python matrix and Playwright status, fix any failures, complete M1–M4 acceptance, then proceed through M5 and M6.
