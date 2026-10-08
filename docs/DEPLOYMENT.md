# Single-organization deployment

LedgerBridge runs one organization's data in one SQLite database. This guide assumes a dedicated host with Python 3.11+, an HTTPS reverse proxy on the same host, and a service account with exclusive access to the data directory. The production server uses Waitress and binds only to 127.0.0.1:8765.

## Initial setup

1. Install runtime dependencies: `python -m pip install -r requirements-prod.txt`.
2. Set ownership of the project and database directory to the service account. Keep the directory accessible only to that account and backup operators. New POSIX data directories are created with mode 0700 and SQLite files with mode 0600.
3. Provision an admin at the terminal with `python -m ledgerbridge.admin add-user admin --role admin`. A password must be at least 15 characters. The first user must be an admin.
4. Configure a trusted TLS reverse proxy for your domain. Pass the original `Host` header and do not expose port 8765 to the network. The app rejects any host or browser Origin different from the configured HTTPS origin. For example, behind an HTTPS virtual host:

```nginx
location / {
    proxy_pass http://127.0.0.1:8765;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_read_timeout 30s;
    client_max_body_size 2m;
}
```

Configure TLS certificates and the rest of the virtual host using your infrastructure's normal process. The app never trusts an arbitrary forwarded host or protocol. Keep the internal HTTP listener on the same trusted host as the proxy.

5. Start `python -m ledgerbridge.server --public-origin https://ledger.example.com`. Replace the example origin with your actual HTTPS origin; omit the trailing slash. Use your service manager to restart after failures. The process refuses to start without a provisioned account, explicit mode, or Waitress.
   Provision at least two people for the workflow: in production, someone who imported or edited a record cannot approve that same record.
6. Verify `GET /api/health` through HTTPS and log in. Only the health route, login assets, and login endpoint are public. Demo records and demo ERP delivery are disabled in production mode.

The app sends Secure, HttpOnly, SameSite=Strict cookies, a per-session CSRF token, a strict content security policy, and HSTS on HTTPS responses. Sessions last eight hours. Accounts lock for 15 minutes after five failed attempts. Use TLS monitoring and reverse-proxy request rate limits, especially for the login route. Audit and exception logs belong in protected, retained host logging. Protect the database and snapshots with encrypted storage if your data policy requires it.

## Accounts

Local operators with database filesystem access can add a reviewer or viewer:

```sh
python -m ledgerbridge.admin add-user analyst --role reviewer
python -m ledgerbridge.admin add-user auditor --role viewer
python -m ledgerbridge.admin set-password analyst
python -m ledgerbridge.admin disable-user analyst
```

Viewers can inspect data; reviewers can import, correct, approve, reject, and reopen; admins can also configure rules and export. Password changes and deactivations revoke sessions. The last active admin cannot be disabled. Admin CLI changes are recorded in the activity log as local operator actions. Protect host access to these commands.

## Backups and recovery

Back up live SQLite using its online backup API; copying only the `.sqlite3` file can miss committed data in the WAL:

```sh
python -m ledgerbridge.maintenance backup --db data/ledgerbridge.sqlite3 --out /secure-backups/ledgerbridge-2026-10-08.sqlite3
```

The command refuses to overwrite a snapshot and verifies `PRAGMA integrity_check`. Schedule it with your job scheduler, store copies off-host with access control, and test recovery. An upgrade from an unversioned database also creates a `pre-v2` snapshot beside the original before changing the schema. Move those snapshots to protected backup storage.

To restore, stop the app, move the current database and its `-wal`/`-shm` sidecars together to a separate recovery directory, and verify that no old sidecars remain at the database path. Place a verified snapshot at the configured database path with the service account's ownership and restricted permissions, then restart. Confirm document counts, user login, an existing export download, and the activity log. Practice this with a nonproduction database first.

## Operational limits

The SQLite deployment is intended for a modest single organization on one host. It has no tenant isolation, external identity provider, or independent tamper-evident audit service. Uploads are text/CSV; scanned PDFs and images need a later OCR path. The target ERP is a local simulator only. A live accounting connector needs a verified API contract, authorization, and end-to-end reconciliation before posting real transactions.
