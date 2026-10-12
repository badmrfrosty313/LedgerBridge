# Roadmap

## Delivered

Local workflow: text/CSV and reviewed XLSX import, deterministic extraction, validation, review, approvals, SQLite storage, audit trail, durable CSV snapshots, and a separate simulated ERP with reconciled, idempotent import receipts.

Allocation workflow: structured reviewer allocation rows, exact deterministic percentage-to-cent previews, audited saved splits, admin-managed reusable templates, total-change invalidation, stale-revision checks, independent approval, and persisted allocation revalidation before approval/export. The legacy CSV intentionally remains one row per source document; allocation-level posting rows are available only in the separately confirmed generic mapped export.

Generic mapping workflow: versioned account mapping, non-persistent dry-run, rejected/unmapped source reporting, preview digest and profile revision checks, immutable mapped exports with provenance, optional allocation expansion, and explicitly invoked local fake-ERP delivery/reconciliation.

Synthetic candidate harness: `python -m pilot.campaign_demo` exercises in-memory XLSX generation through preview, import, exact allocation, different-person approval, mapped dry-run, immutable export, fake ERP receipt and idempotent retry. It reports observed elapsed time and cent totals; it does not claim real-world extraction quality, customer results, or labor savings.

Deployment hardening: explicit runtime modes, user accounts and role checks, server-controlled audit identities, bounded sessions, CSRF tokens, authenticated local tests, a WSGI production path behind TLS, schema version checks, and verified SQLite backups.

Closed pilot kit: synthetic CSV ground truth, exception and reconciliation acceptance runner, manual walkthrough and scorecard, plus a scoped security review with remaining release gates.

## Next product capabilities

- Local OCR for images/PDFs, tested against bounded inputs and a labeled fixture corpus.
- Verified third-party accounting contracts and real connector implementations are not included. This campaign branch includes a generic simulated-ledger mapping profile, dry-run, immutable mapped snapshots, and local fake-ERP delivery; it is not MIP-specific support.
- Optional provider-neutral AI extraction with structured outputs, deterministic validation, reviewer approval, quality metrics, and MCP tools.
- Organization isolation, SSO/MFA, PostgreSQL, durable external audit storage, and coordinated migrations for multi-tenant or larger deployments.

These are future capabilities, not release claims. See [V2_RELEASE_CANDIDATE.md](V2_RELEASE_CANDIDATE.md) for the current campaign scope and remaining release gates.
