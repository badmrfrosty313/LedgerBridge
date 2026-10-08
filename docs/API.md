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
| PATCH | `/api/documents/{id}` | Reviewer+ | `{fields,revision}` |
| POST | `/api/documents/{id}/approve` | Reviewer+ | `{revision}` |
| POST | `/api/documents/{id}/reject` | Reviewer+ | `{revision,reason}` |
| POST | `/api/documents/{id}/reopen` | Reviewer+ | `{revision}` |
| GET | `/api/rules` | Viewer+ | Rules and revision |
| PATCH | `/api/rules` | Admin | `{rules,revision}` |
| GET | `/api/events` | Viewer+ | Latest 500 events |
| POST | `/api/exports` | Admin | Snapshot approved records |
| GET | `/api/exports` | Viewer+ | Saved exports |
| GET | `/api/exports/{id}/download` | Viewer+ | Saved CSV snapshot |

Local demo and authenticated local modes also offer `POST /api/demo`, `GET /api/bridge/status`, `GET /api/bridge/deliveries`, and `POST /api/exports/{id}/send-demo`. The demo is disabled on the public deployment path.

Money fields in edits are integer cents: `subtotal_cents`, `tax_cents`, `total_cents`. Other editable fields: `vendor`, `document_number`, `date`, `account_code`, `department`, `notes`. Dates use YYYY-MM-DD. A stale revision or validation conflict returns 409; bad input 400; an unauthenticated request 401; missing permission/token or wrong origin/host 403; missing resource 404; excessive body 413; wrong content type 415. Errors return `{"error":"explanation"}`.

Imports and exports use SQLite transactions. Exports revalidate approvals inside the transaction and lock exported records. Saved snapshots remain downloadable and demo ERP retries use stable batch IDs.
