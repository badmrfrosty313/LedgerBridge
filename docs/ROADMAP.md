# Roadmap

## Delivered

Local workflow: text/CSV import, deterministic extraction, validation, review, approvals, SQLite storage, audit trail, durable CSV snapshots, and a separate fake ERP with reconciled, idempotent import receipts.

Deployment hardening: explicit runtime modes, user accounts and role checks, server-controlled audit identities, bounded sessions, CSRF tokens, authenticated local tests, a WSGI production path behind TLS, schema version checks, and verified SQLite backups.

## Next product capabilities

- Local OCR for images/PDFs and Excel import, each tested against bounded inputs and a labeled fixture corpus.
- Configurable ERP field mapping, a connector interface, dry-run preview, and verified third-party contracts. MIP-specific support needs a documented schema and account access.
- Optional provider-neutral AI extraction with structured outputs, deterministic validation, reviewer approval, quality metrics, and MCP tools.
- Organization isolation, SSO/MFA, PostgreSQL, durable external audit storage, and coordinated migrations for multi-tenant or larger deployments.

These are future capabilities, not release claims.
