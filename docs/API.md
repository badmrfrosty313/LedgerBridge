# Local JSON API

Base URL: `http://127.0.0.1:8765`. Mutations require `Content-Type: application/json` and an `actor` label. Browser requests must be same-origin. No authenticated identity or multi-tenant isolation exists in v0.1.

| Method | Route | Purpose |
|---|---|---|
| GET | `/api/health` | Version and service status |
| GET | `/api/documents` | List records and current validation issues |
| GET | `/api/documents/{id}` | Record, source, and history |
| POST | `/api/import/text` | Import `{text, source_name, actor}` |
| POST | `/api/import/csv` | Import `{text, source_name, actor}` |
| POST | `/api/demo` | Load eight fixtures; idempotent exact imports |
| PATCH | `/api/documents/{id}` | Correct `{fields, revision, actor}` |
| POST | `/api/documents/{id}/approve` | Approve `{revision, actor}` |
| POST | `/api/documents/{id}/reject` | Reject `{revision, actor, reason}` |
| POST | `/api/documents/{id}/reopen` | Reopen `{revision, actor}` |
| GET | `/api/rules` | Business rules and revision |
| PATCH | `/api/rules` | Replace `{rules, revision, actor}` |
| GET | `/api/events` | Latest 500 events |
| POST | `/api/exports` | Export all currently approved records with `{actor}` |
| GET | `/api/exports` | Saved export metadata |
| GET | `/api/exports/{id}/download` | Download stored CSV snapshot |

Money fields in record edits are integer cents: `subtotal_cents`, `tax_cents`, `total_cents`. Other editable fields: `vendor`, `document_number`, `date`, `account_code`, `department`, `notes`. A blank optional amount is null. Dates use YYYY-MM-DD. Reject invalid dates or amounts; do not silently round.

Revisions implement optimistic concurrency. A stale revision returns HTTP 409. Validation conflicts also return 409. Invalid inputs return 400, forbidden host/origin requests 403, unknown records/routes 404, excessive bodies 413, wrong content types 415. Errors use `{ "error": "explanation" }`.

Imports and exports use database transactions. Exports only include approved records and revalidate inside the transaction. Exported records cannot be edited, reopened, rejected, or exported again. Previously saved exports remain downloadable.
