# LedgerBridge

A configurable local workflow for importing, validating, reviewing, and exporting financial records across business systems.

## Run in two minutes

Requires **Python 3.11+**. The first release uses only Python's standard library; there are no packages, API keys, or cloud services to install.

```powershell
git clone https://github.com/badmrfrosty313/LedgerBridge.git
cd LedgerBridge
python -m ledgerbridge.server
```

On Windows, use `py -m ledgerbridge.server` if `python` is not available, or double-click `start_windows.bat`.

Open **http://127.0.0.1:8765**. Stop the server with Ctrl+C.

## Try the complete workflow

1. Click **Load 8 demo documents**. The examples use anonymized structures from the earlier Invoice-to-Ledger-Automation prototype.
2. Select the software invoice. Set account code to `5100`, department to `Technology`, and save corrections.
3. Resolve any remaining validation issues, then **Approve record**.
4. Open **Export history** and click **Create approved CSV**.
5. Download the CSV. Its records are now locked as exported; the snapshot remains available after restarting.
6. Inspect **Activity log** for the import, correction, approval, and export events.

The telecom line-detail example has no date; it deliberately requires a reviewer correction. Codes are examples, not a prescribed chart of accounts.

## What works

- Paste document text for deterministic extraction of vendor/payee, document number, date, subtotal, tax, and total.
- Import CSV batches atomically; malformed rows roll back the batch.
- Track draft, approved, rejected, and exported records in SQLite.
- Configure organization, currency, required fields, allowed account codes/departments, approval limits, and reconciliation tolerance.
- Block approval on missing fields, mismatched totals, unsupported codes, excessive amounts, and potential duplicate payments.
- Correct fields, reject records with reasons, reopen reviews, and inspect source text and record history.
- Invalidate approvals after edits or business-rule changes. Recheck validation inside the export transaction.
- Export approved records once into a durable CSV snapshot. Later duplicates are checked against exported records.
- Record before/after fields, reviewer labels, timestamps, rules changes, and export snapshots in the audit history.
- Reject stale edits/reviews using revision numbers and neutralize formula-like strings in spreadsheet exports.

Exact reimports open the existing record instead of creating another. Potential duplicates use vendor + document number, or vendor + date + total when both documents have no number. This is a heuristic: reviewers decide which copy to reject.

## Try the separate demo ERP

In a second terminal in the same repository, run:

```powershell
python -m ledgerbridge.mock_erp
```

In **Export history**, click **Send to demo ERP** beside a saved export. A separate database receives the batch and returns a reconciled receipt. Click **Verify / retry demo ERP** to confirm the same receipt without posting duplicate records. Inspect the target ledger at http://127.0.0.1:8766/api/ledger.

The connector validates the target's batch ID, record count, and payload hash before recording successful delivery. If delivery succeeded but the local receipt was lost, retrying recovers the target receipt. This is a simulated target API, not MIP or another real accounting system. The target port can be changed using matching `--port` (mock ERP) and `--demo-erp-port` (LedgerBridge) options.

## CSV import format

Required headers: `vendor,date,total`.

Optional headers: `document_number,subtotal,tax,account_code,department,notes`.

Dates must be `YYYY-MM-DD`. Monetary amounts are decimal currency, not cents. Maximum 500 rows / 1 MB per CSV. See `examples/sample_import.csv`.

```csv
vendor,date,total,document_number,subtotal,tax,account_code,department,notes
Northstar Services LLC,2026-10-01,319.93,NS-1001,299.00,20.93,5100,Technology,Monthly services
```

## Data and deployment

Data lives in `data/ledgerbridge.sqlite3` by default and is excluded from Git. Back up the database while the server is stopped. To use a separate workspace or port:

```powershell
python -m ledgerbridge.server --db data/another-business.sqlite3 --port 8766
```

This release is a **local single-user prototype** bound to 127.0.0.1. Reviewer names are audit labels, not authenticated identities. The audit history is application-managed, not cryptographically tamper-proof. Do not expose it as a public or multi-user service. No records are posted directly to accounting software.

PDF/image OCR, Excel ingestion, real ERP adapters, authenticated roles, AI-assisted extraction, MCP tools, and cloud hosting are not implemented in this release. Existing parser notes remain attached to the original extraction; live validation uses corrected fields. Credit notes and multiple currencies in one workspace require dedicated future workflows.

## Architecture

- `ledgerbridge/extraction/`: reusable document parser and classifier from Invoice-to-Ledger-Automation.
- `ledgerbridge/core.py`: deterministic validation, transactional workflow, SQLite storage, audit history, CSV adapter.
- `ledgerbridge/server.py`: JSON API and static file server with localhost origin/host checks.
- `ledgerbridge/static/`: responsive browser review workspace, no build tools or external assets.
- `ledgerbridge/demo.json`: eight anonymized semantic fixtures. Original images/PDFs are not included.
- `tests/`: fixture regressions, business workflow failures, restart persistence, export boundaries, and live HTTP integration.

The extraction layer produces proposals; the workflow layer owns approval; the export layer produces reviewed snapshots. Future AI/MCP and ERP connectors can call these boundaries without bypassing deterministic validation.

## Validation

```powershell
python -m unittest discover -s tests -v
```

GitHub Actions runs the same tests on Windows and Linux. No cloud account is needed.

See `docs/API.md` for endpoints and `docs/ROADMAP.md` for the next implementation slices.
