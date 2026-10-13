# LedgerBridge 2.0

[Earlier one-page feature overview (PDF, originally v0.2.0)](docs/LedgerBridge_One_Page_Overview.pdf)

LedgerBridge imports business documents, finds validation exceptions, records human review, creates durable CSV exports, and can demonstrate delivery to a separate simulated ERP. The code supports a single organization per database. Demo and pilot documents are fully invented synthetic examples.

**Version 2.0.0:** a local-first, portfolio-oriented financial document review application with safe Excel intake, exact-cent allocations and templates, independent approval, a reviewer workspace, immutable mapped exports and simulated ERP reconciliation. It is not a live accounting integration or a security-certified system for confidential customer records. Support, response times, compatibility, and future updates are not guaranteed. Licensed under [MIT](LICENSE); see [dependency attribution](THIRD_PARTY_NOTICES.md), [release notes](docs/RELEASE_NOTES.md), and [security review](docs/SECURITY_REVIEW.md).

## Explore locally

Python 3.11+ is required. On Windows, double-click `start_windows.bat`, or run:

```powershell
python -m ledgerbridge.server --local-demo
```

Open http://127.0.0.1:8765 and load the eight examples. This explicitly selected local mode has no login and only listens on loopback. Do not place real financial documents in the demo database.
The demo uses its own `data/ledgerbridge-demo.sqlite3` and cannot be pointed at the production database.

## Authenticated local testing

Create an admin with an interactive password prompt:

```powershell
python -m ledgerbridge.admin --db data/ledgerbridge-local.sqlite3 add-user admin --role admin
python -m ledgerbridge.admin --db data/ledgerbridge-local.sqlite3 add-user second-reviewer --role reviewer
python -m ledgerbridge.server --local-auth
```

Open http://127.0.0.1:8765 and sign in. Passwords stay out of shell history. `--local-auth` uses a separate local database by default and enforces another person's approval; it is for testing over loopback HTTP. Production needs an HTTPS reverse proxy. A separate database can be selected with `--db PATH`.

## Production deployment

Follow [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md). Production startup is explicit and requires an existing admin, Waitress, a configured HTTPS origin, and a TLS reverse proxy. The server binds to 127.0.0.1; it refuses to start without a mode. Reviewer identities are verified server-side, sessions have a limited lifetime, changing passwords revokes sessions, and writes require per-session request tokens. Roles are viewer, reviewer, and admin. Business rules and exports require admin.

```powershell
python -m pip install -r requirements-prod.txt
python -m ledgerbridge.server --public-origin https://ledger.example.com
```

This is a deployable single-organization service, not a claim of compliance certification. Provision a real domain, TLS, host hardening, restricted database access, monitoring, backup storage, and a restore drill before processing real data. Direct integrations with live accounting systems require their verified schemas and authorization.

## Workflow

1. Paste document text, import CSV, or upload a bounded `.xlsx` workbook. Excel uploads show a row-level preview and require explicit confirmation before draft records are created.
2. Resolve missing fields, duplicate candidates, reconciliation differences, and account code exceptions. Reviewers can optionally preview exact percentage-to-cent cost splits, save them under a revision check, and apply reusable admin-managed templates; any split change requires an independent approval.
3. Approve a record; changing it or the business rules clears approval.
4. An admin exports approved records into an immutable CSV snapshot, or uses the generic simulated-ledger mapping dry-run and explicit confirmation workflow.
5. In local mode, run `python -m ledgerbridge.mock_erp` in another terminal. Use **Send to demo ERP** to post a confirmed snapshot to a separate ledger. Retry verifies the same receipt without double posting.

Exact reimports open the original record. Potential duplicates use vendor + document number, or vendor + date + total when neither has a document number. Reviewers decide which copy to reject.

CSV and `.xlsx` import require `vendor,date,total`; optional columns are `document_number,subtotal,tax,account_code,department,notes`. Excel accepts exactly one worksheet, rejects formulas and unsafe/oversized workbooks, and never executes macros or external links. Dates use YYYY-MM-DD and monetary amounts use decimal currency with no fractional-cent rounding. See [sample_import.csv](examples/sample_import.csv). Import limits: 500 rows and 1 MB. The browser and API reject invalid dates, fractional cents, and stale revisions; imported records remain drafts and require normal independent approval.

Cost allocations are integrity-checked before approval and export, and changing a source total removes stale splits and requires a new allocation review. The legacy CSV export deliberately remains one row per source document; it does **not** emit allocation-level rows. The separately confirmed generic simulated-ledger export can expand saved splits when that profile option is enabled.

Negative credit totals remain rejected unless an administrator explicitly enables the backward-compatible `allow_credits` business rule. When enabled, credits still require ordinary validation, exact allocation reconciliation where configured, independent approval, immutable export, and simulated receipt; zero totals remain invalid.

Data resides in `data/ledgerbridge.sqlite3` unless `--db` selects another path. It is excluded from Git. Back up using the SQLite snapshot command in the deployment guide. Upgrading supported older document databases creates a checked pre-migration snapshot before schema changes.

## Validation

```powershell
python -m unittest discover -s tests -v
```

GitHub Actions runs Python tests on Windows and Linux, plus a browser workflow that covers authenticated login, import, review, export, demo ERP delivery/retry, rule changes, and mobile-width layout.

Run the [closed pilot kit](pilot/README.md) with `python -m pilot.run` to check a synthetic exception queue, two-person approval, export totals, and restore. The [security review](docs/SECURITY_REVIEW.md) records controls tested and remaining release gates.

The [API reference](docs/API.md) describes the endpoints and permissions. The [v2 campaign candidate guide](docs/V2_RELEASE_CANDIDATE.md) documents the synthetic XLSX-to-simulated-ledger demonstration and release gates. [ROADMAP.md](docs/ROADMAP.md) tracks excluded future work including PDF/image OCR, AI/MCP features, and verified real-accounting connector requirements.
