# v0.2.0 release pass — 2026-10-08 (historical)

## v2.0 candidate gates — not a release authorization

- [ ] Review and merge the campaign branch only after owner approval; no automatic merge.
- [ ] Verify the final Windows/Linux Python 3.11/3.12 matrix and Playwright job are completed and green for the candidate commit.
- [ ] Re-run the original synthetic `$638.00` pilot, `python -m pilot.campaign_demo`, the complete Python suite, and `python scripts/release.py --check`.
- [ ] Review v0.2.0 database backup/migration/restore, independent approval, corrupted allocation rejection, immutable exports, and simulated ERP idempotency evidence.
- [ ] Inspect all added fixtures, docs, logs, and screenshots for synthetic-only data and secrets; document remaining operational/security risks.
- [ ] Obtain separate owner authorization before changing package version, creating a release/tag, deploying, using real financial records, or enabling any live accounting connection.

The v2 workflow is a release-candidate implementation branch, not a completed security certification or public deployment.

- MIT license added with Kyle Hawkins's copyright notice.
- Earlier parser lineage and separately installed dependency licenses documented in `THIRD_PARTY_NOTICES.md`.
- Eight demo fixtures replaced with fully invented text, names, amounts, dates, and identifiers. The pilot corpus is also invented.
- Package version and health response aligned to 0.2.0.
- Maintenance and support expectations added to the README and release notes.
- All 10 pre-release commits reachable from the repository branches were checked: 78 unique file blobs, no fetch failures, and no matches for private keys, common GitHub/AWS/Slack tokens, or credential-bearing URLs. No database, original document, image, or private-key artifacts appeared in tracked history. Test credentials in the automated suites are synthetic examples, not deployed accounts. This pattern scan is not a guarantee against every possible secret.
- Python tests, pilot acceptance, browser workflow, and production startup gate the release in GitHub Actions. `scripts/release.py --check` verifies release metadata without network access.
- The main branch's successful CI run creates a version tag and release. The publisher never moves an existing tag. Repository visibility is a separate action.

Company-specific configuration, real accounting integration, and operational controls remain documented in the deployment guide and security review. They are not prerequisites to this portfolio release.
