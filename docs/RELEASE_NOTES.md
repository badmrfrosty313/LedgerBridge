# LedgerBridge v2.0.0

LedgerBridge 2.0 is a local-first financial document review and accounting automation portfolio release. The included data, validation runs and simulated accounting workflow are synthetic. **It does not connect to live accounting, banking or payroll systems.**

## Highlights

- **Safe Excel intake:** bounded single-sheet XLSX import with row-level preview, formula and unsafe-file rejection, one-use session-owned confirmation, and audited draft creation.
- **Exact allocation engine:** percentage splits reconcile to integer cents with deterministic rounding, persisted reusable templates, explicit preview/save, independent approvals, and automatic allocation re-review when source totals change.
- **Generic mapped exports:** administrator-controlled, versioned mapping profile, read-only dry-run, reviewer separation, immutable allocation-aware export, and full cent reconciliation.
- **Simulated accounting delivery:** local mock ERP validates mapped records, accepts idempotent retries, returns receipts, and exposes source-to-destination reconciliation. No live connector or third-party posting.
- **Reviewer workspace:** exceptions, search/filter, history and audit trail, responsive allocation controls, and explicit review boundaries.
- **Data security and recovery:** role-based sessions, CSRF protection, SQLite transactional migrations and pre-upgrade backups, bounded parsers, and fail-closed financial validation.

## Verified acceptance

- GitHub Actions passed on the v2 campaign branch, with Python 3.11/3.12 on Windows and Linux, an authenticated Playwright browser journey, and a Waitress production-startup smoke check. See the repository's workflow history for the exact release commit's final checks.
- 79 Python tests reported passing on the reviewed campaign checkpoint.
- Original synthetic pilot: 11 imported documents, eight exported records totaling **$638.00**, three rejected; restore validation included.
- Synthetic end-to-end campaign: 10,001 cents from intake through allocation, mapped export and local mock-ERP receipt, with zero-cent difference and an idempotent retry.
- Five independent source-review findings were corrected and verified before release preparation; see Issues #8 and the release checklist.

## Limitations

This is a portfolio-oriented single-organization tool, not a certification or authorization for real financial data. Legacy CSV exports remain one row per document; expanded allocations require the separate mapped format. The ERP is a simulator. SSO/MFA, tamper-resistant external audit storage, live accounting integration, operational backups, and real-world extraction validation are not provided. Negative credits require explicit admin opt-in. OCR/AI (M7) is excluded.

For setup, demo workflow, engineering caveats and reproducible benchmarks, consult the [README](../README.md), [v2 candidate guide](V2_RELEASE_CANDIDATE.md), and [security review](SECURITY_REVIEW.md).

## Historical v0.2.0 release

Version 0.2.0 introduced structured text/CSV document review, deterministic extraction and exception checks, independent approval, authenticated audit trails, immutable CSV snapshots, Waitress production startup, and a fully invented synthetic pilot. The historical release remains available under its immutable `v0.2.0` tag.
