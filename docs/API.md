# JSON API

Production base URL is the configured HTTPS origin. Authenticated requests use the browser session cookie; `GET /api/session` returns the signed-in username, role, and per-session CSRF token. Every POST/PATCH after login sends that token in `X-CSRF-Token`. The server supplies the audit actor; request-body `actor` is ignored in authenticated mode.

| Method | Route | Access | Purpose |
|---|---|---|---|
| GET | `/api/health` | Public | Liveness and version |
| POST | `/api/login` | Public | Sign in with `{username,password}` |
| GET | `/api/session` | Signed in | Username, role, request token |
| POST | `/api/logout` | Signed in + token | Revoke session |
| GET | `/api/documents` | Viewer+ | Records and current issues |
| GET | `/api/documents/{id}` | Viewer+ | Record, source, history |
| POST | `/api/import/text` | Reviewer+ | `{text,source_name}` |
| POST | `/api/import/csv` | Reviewer+ | `{text,source_name}` |
| POST | `/api/import/xlsx/preview` | Reviewer+ | `{content_base64,source_name}`; validate one bounded worksheet without persistence |
| POST | `/api/import/xlsx/confirm` | Reviewer+ | `{preview_token}`; import a clean preview as draft records |
| POST | `/api/documents/{id}/allocations/preview` | Reviewer+ | `{items}`; deterministic exact-cent allocation preview, no write |
| POST | `/api/documents/{id}/allocations/confirm` | Reviewer+ | `{items,revision}`; save a reviewed split and require new independent approval |
| GET | `/api/allocation-templates` | Reviewer+ | Read reusable allocation templates |
| POST | `/api/allocation-templates` | Admin | `{name,items,revision?}`; save or revision-check a reusable template |
| PATCH | `/api/documents/{id}` | Reviewer+ | `{fields,revision}` |
| POST | `/api/documents/{id}/approve` | Reviewer+ | `{revision}` |
| POST | `/api/documents/{id}/reject` | Reviewer+ | `{revision,reason}` |
| POST | `/api/documents/{id}/reopen` | Reviewer+ | `{revision}` |
| GET | `/api/rules` | Viewer+ | Rules and revision |
| PATCH | `/api/rules` | Admin | `{rules,revision}` |
| GET | `/api/mapping-profile` | Reviewer+ | Read current generic simulated-ledger mapping profile |
| POST | `/api/mapping/profile` | Admin | `{profile,revision}`; revision-checked mapping update |
| GET | `/api/mapping/dry-run` | Reviewer+ | Non-persistent mapped rows, rejected rows, profile revision, source/mapped signed-cent totals, and preview hash |
| POST | `/api/mapping/exports` | Reviewer+ | `{preview_id,revision}`; a reviewer other than the last profile editor recomputes the dry-run and creates the immutable mapped snapshot |
| GET | `/api/reconciliation` | Signed in (local demo) | Source → mapped export → local simulated ERP receipt totals, differences, and receipt integrity state |
| GET | `/api/events` | Viewer+ | Latest 500 events |
| POST | `/api/exports` | Admin | Snapshot approved records |
| GET | `/api/exports` | Viewer+ | Saved exports |
| GET | `/api/exports/{id}/download` | Viewer+ | Saved CSV snapshot |

Local demo and authenticated local modes also offer `POST /api/demo`, `GET /api/bridge/status`, `GET /api/bridge/deliveries`, and `POST /api/exports/{id}/send-demo`. The demo is disabled on the public deployment path.

Money fields in edits are integer cents: `subtotal_cents`, `tax_cents`, `total_cents`. Other editable fields: `vendor`, `document_number`, `date`, `account_code`, `department`, `notes`. Dates use YYYY-MM-DD. A stale revision or validation conflict returns 409; bad input 400; an unauthenticated request 401; missing permission/token or wrong origin/host 403; missing resource 404; excessive body 413; wrong content type 415. Errors return `{"error":"explanation"}`.

Imports and exports use SQLite transactions. Exports revalidate approvals inside the transaction and lock exported records. Saved snapshots remain downloadable and demo ERP retries use stable batch IDs.

Excel intake accepts `.xlsx` only, with one worksheet, a 1 MB source limit, 500 rows, and the same `vendor,date,total` schema as CSV. The preview reports row-level mapping/validation failures; formulas are rejected and no record is created until a reviewer confirms a clean preview. Excel rows never bypass normal validation, review, independent approval, or audit history.

The generic simulated-ledger v1 profile maps approved source account codes to invented target codes. Dry-run is read-only; confirmation rechecks both the profile revision and a digest of the current source records inside the export transaction. Optional allocation expansion emits one non-zero posting row per saved destination. The resulting CSV is an immutable export accepted only by the local simulated ERP; it is not a live accounting connector. The older default CSV remains one row per source document.

The reconciliation endpoint is available only when the local simulated bridge is configured. It compares signed integer-cent source and mapped totals, checks the immutable CSV content hash and total, and—after delivery—compares the mock ERP's receipt hash, row count, and received cent sum. `not_sent`, unavailable target, and mismatches remain visible states; they are never silently reported as reconciled.
