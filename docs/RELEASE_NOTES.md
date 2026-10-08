# LedgerBridge v0.2.0

Completed portfolio release for a single-organization document review and CSV export workflow.

- Text and CSV imports, deterministic extraction, validation exceptions, duplicate detection, review, and immutable CSV exports.
- Verified accounts and roles, server-owned audit identities, CSRF, independent approval, session revocation, and explicit deployment modes.
- Waitress production startup behind a trusted HTTPS proxy, SQLite online backups, and documented recovery.
- Closed pilot kit: 11 synthetic cases, 8 approved export rows totaling USD 638.00, exception correction and exclusion, rollback, exact reimport, and backup restore.
- Fully invented demo fixtures, MIT licensing, dependency attribution, and a scoped security review with documented operational gates.

This is a portfolio project maintained as time permits. Support, response times, compatibility, and future updates are not guaranteed. There is no live accounting connector, OCR/Excel ingestion, multi-tenant hosting, SSO/MFA, or external tamper-resistant audit storage. Read the deployment guide and security review before using real financial records.

Run `python -m pilot.run` for isolated acceptance, or follow the README for the local demo. GitHub Actions checks Windows/Linux Python tests, browser behavior, and production startup before creating a release tag from main. Existing release tags are never moved automatically.
