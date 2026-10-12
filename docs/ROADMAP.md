# Roadmap

## Delivered

Local workflow: text/CSV and reviewed XLSX import, deterministic extraction, validation, review, approvals, SQLite storage, audit trail, durable CSV snapshots, and a separate fake ERP with reconciled, idempotent import receipts.

Allocation groundwork: deterministic percentage-to-cent previews, audited saved splits, reviewer templates, total-change invalidation, and approval/export integrity checks. The existing CSV export intentionally remains one row per source document; split allocation rows are not yet exported.

Deployment hardening: explicit runtime modes, user accounts and role checks, server-controlled audit identities, bounded sessions, CSRF tokens, authenticated local tests, a WSGI production path behind TLS, schema version checks, and verified SQLite backups.

Closed pilot kit: synthetic CSV ground truth, exception and reconciliation acceptance runner, manual walkthrough and scorecard, plus a scoped security review with remaining release gates.

## Next product capabilities

- Local OCR for images/PDFs, tested against bounded inputs and a labeled fixture corpus.
- Verified third-party accounting contracts and real connector implementations are not included. This campaign branch includes a generic simulated-ledger mapping profile, dry-run, immutable mapped snapshots, and local fake-ERP delivery; it is not MIP-specific support.
- Optional provider-neutral AI extraction with structured outputs, deterministic validation, reviewer approval, quality metrics, and MCP tools.
- Organization isolation, SSO/MFA, PostgreSQL, durable external audit storage, and coordinated migrations for multi-tenant or larger deployments.

These are future capabilities, not release claims.
