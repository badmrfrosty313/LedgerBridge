# LedgerBridge v0.2.0

## LedgerBridge 2.0 campaign candidate — unreleased

The current development branch extends v0.2.0 with reviewed XLSX preview/import, exact allocations and reusable templates, a versioned generic simulated-ledger profile and dry-run, immutable allocation-aware mapped exports, a synthetic XLSX-to-mock-ERP reconciliation harness, and additional reviewer/security coverage. These changes are not a published package or release. See [V2_RELEASE_CANDIDATE.md](V2_RELEASE_CANDIDATE.md) and [CAMPAIGN_STATUS.md](CAMPAIGN_STATUS.md). No real accounting system is connected.

## Historical v0.2.0 release notes

Completed portfolio release for a single-organization document review and CSV export workflow.

- Text and CSV imports, deterministic extraction, validation exceptions, duplicate detection, review, and immutable CSV exports.
- Verified accounts and roles, server-owned audit identities, CSRF, independent approval, session revocation, and explicit deployment modes.
- Waitress production startup behind a trusted HTTPS proxy, SQLite online backups, and documented recovery.
- Closed pilot kit: 11 synthetic cases, 8 approved export rows totaling USD 638.00, exception correction and exclusion, rollback, exact reimport, and backup restore.
- Fully invented demo fixtures, MIT licensing, dependency attribution, and a scoped security review with documented operational gates.

At the time of the v0.2.0 release, there was no live accounting connector, OCR/Excel ingestion, multi-tenant hosting, SSO/MFA, or external tamper-resistant audit storage. Current campaign behavior and residual limitations are described above and in the security review.

Run `python -m pilot.run` for isolated acceptance, or follow the README for the local demo. GitHub Actions checks Windows/Linux Python tests, browser behavior, and production startup before creating a release tag from main. Existing release tags are never moved automatically.
