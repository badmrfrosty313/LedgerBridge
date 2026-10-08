# LedgerBridge

LedgerBridge imports business documents, finds validation exceptions, records human review, creates durable CSV exports, and can demonstrate delivery to a separate simulated ERP. The code supports a single organization per database. Demo and pilot documents are fully invented synthetic examples.

This is a completed portfolio project, maintained as time permits. Support, response times, compatibility, and future updates are not guaranteed. It is released under [MIT](LICENSE); see [dependency attribution](THIRD_PARTY_NOTICES.md) and [release notes](docs/RELEASE_NOTES.md).

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

1. Paste document text or import a CSV. A reviewer checks the extracted proposal.
2. Resolve missing fields, duplicate candidates, reconciliation differences, and account code exceptions.
3. Approve a record; changing it or the business rules clears approval.
4. An admin exports approved records into an immutable CSV snapshot.
5. In local mode, run `python -m ledgerbridge.mock_erp` in another terminal. Use **Send to demo ERP** to post the snapshot to a separate ledger. Retry verifies the same receipt without double posting.

Exact reimports open the original record. Potential duplicates use vendor + document number, or vendor + date + total when neither has a document number. Reviewers decide which copy to reject.

CSV import requires `vendor,date,total`; optional columns are `document_number,subtotal,tax,account_code,department,notes`. Dates use YYYY-MM-DD and monetary amounts use decimal currency. See [sample_import.csv](examples/sample_import.csv). Import limits: 500 rows and 1 MB. The browser and API reject invalid dates, fractional cents, and stale revisions.

Data resides in `data/ledgerbridge.sqlite3` unless `--db` selects another path. It is excluded from Git. Back up using the SQLite snapshot command in the deployment guide. Changes to older unversioned databases create a snapshot before upgrading.

## Validation

```powershell
python -m unittest discover -s tests -v
```

GitHub Actions runs Python tests on Windows and Linux, plus a browser workflow that covers authenticated login, import, review, export, demo ERP delivery/retry, rule changes, and mobile-width layout.

Run the [closed pilot kit](pilot/README.md) with `python -m pilot.run` to check a synthetic exception queue, two-person approval, export totals, and restore. The [security review](docs/SECURITY_REVIEW.md) records controls tested and remaining release gates.

The [API reference](docs/API.md) describes the endpoints and permissions. [ROADMAP.md](docs/ROADMAP.md) tracks PDF/image OCR, Excel import, AI/MCP features, and real accounting connectors.
