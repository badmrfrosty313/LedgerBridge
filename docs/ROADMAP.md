# Implementation roadmap

## Delivered: local review workflow

Document text and CSV import; configurable validation; SQLite persistence; exception review; approvals and rejection; audit history; immutable CSV exports; responsive UI; regression and live API tests; Windows launcher; CI.

## Next: document ingestion

Reuse and evaluate the earlier local OCR engine against generated invoice images and PDFs. Add bounded page/image processing, OCR confidence notes, native PDF text extraction, and Excel import. Keep original documents out of Git. Preserve source provenance and show confidence as an observation, not a promise of accuracy.

## Next: legacy bridge demonstration

Build a fake ERP with a separate data store and a documented import API. Add field mapping, a connector contract, dry-run previews, reconciliation receipts, retry/idempotency behavior, and error recovery. Demonstrate the same approved records flowing to different configured target formats. MIP-specific support remains an optional adapter requiring a verified target schema.

## Next: AI operations layer

Add a provider-neutral extraction adapter with schema-validated output, deterministic comparison against totals, and explicit reviewer approval. Implement MCP tools for list exceptions, inspect record, propose correction, and create export. Keep posting actions behind the reviewed workflow. Measure extraction correctness, exception rate, and review time on a fixed fixture corpus.

## Next: portfolio deployment

Adopt FastAPI and React/TypeScript when splitting the API/UI becomes worthwhile. Add PostgreSQL, migrations, authenticated roles, organization isolation, deployment configuration, Docker, and an Azure demo using synthetic data. Add production-grade serving, retention, backups, and access controls before external users or real financial data.

These are planned capabilities, not claims about the current release.
