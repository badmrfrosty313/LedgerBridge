# Security review — 2026-10-08

Scope: LedgerBridge's single-organization Python service, browser UI, SQLite workflow, local simulated connector, deployment instructions, and dependency manifest on this branch. This is a code and automated-behavior review, not a penetration test, an independent audit, or a certification. No live company environment or real financial records were tested.

## Reviewed boundaries

| Area | Evidence and result |
|---|---|
| Authentication and authorization | Server-owned session identity, hashed tokens, password derivation, role checks, session revocation, lockout, and independent approval in both authenticated modes are exercised in `tests/test_security.py` and the browser CI flow. Login successes/failures and logout now leave audit entries without passwords or tokens. |
| Browser request protection | Exact public Host and Origin checks, cross-site fetch denial, Secure/HttpOnly/SameSite cookies, CSP, CSRF on authenticated writes, and output escaping in the UI. WSGI now ignores spoofed `HTTP_CONTENT_LENGTH` and `HTTP_CONTENT_TYPE` aliases and uses the canonical WSGI body metadata. |
| Input and output | JSON size and shape limits, CSV row/size bounds, typed cents and dates, SQL parameters, and spreadsheet formula escape. Leading NUL is now escaped; see `tests/test_workflow.py`. |
| Financial integrity | Database transactions, revision checks, separate approver in production, validation before approval and export, immutable export snapshots, and duplicate flags. `pilot/run.py` exercises exception correction, exclusion, export total, and restore against synthetic ground truth. |
| Operations | Fixed loopback binding, public HTTPS origin requirement, pinned Waitress 3.0.2, checked SQLite online backups. Authenticated local mode now defaults to `data/ledgerbridge-local.sqlite3`, separate from the deployment default. |

## Open risks and release gates

| Priority | Risk | Before real operational use |
|---|---|---|
| High | A filesystem administrator can edit the SQLite audit table and financial records. | Forward security and business events to protected external storage; test access, retention, and investigation procedures. A hash chain in the same writable database would not solve administrator tampering. |
| High | There is no verified import contract for any real accounting system; exports are generic CSV, and the connector is a simulator. | Validate mapping, accepted rows, rejects, corrections, and reconciliation with the target system in a nonproduction environment. Keep live posting disabled until signed off. |
| High | Real-world extraction quality is unknown beyond a small test corpus, and document formats are limited. | Label permitted representative samples; measure missing/wrong fields and reviewer time; keep humans approving every item. |
| Medium | Account lockout can be used to deny a known user access. Login work is expensive and in-process concurrency limited. | Put rate limits and alerting at the trusted proxy, test recovery and the user unlock/password reset process. |
| Medium | Availability and data recovery depend on the deployment operator. | Automate encrypted off-host backups, monitor failures and disk capacity, run restore drills, define recovery objectives and incident ownership. |
| Medium | Local password accounts lack SSO/MFA and the audit log contains document fields. | Apply the buyer's identity, access-review, retention, and data-handling requirements; minimize/ship protected logs as appropriate. |
| Medium | Python, Waitress, GitHub Actions, the host, and reverse proxy require ongoing updates. | Run dependency advisories and patch management, review configuration and proxy/TLS behavior before exposure. |

Findings addressed in this pass: canonical WSGI body headers, spreadsheet NUL escaping, local-auth default database separation, and authentication event coverage. Automated tests check those changes. Remaining risks are explicit deployment and product gates, not evidence of a completed independent security assessment. Guidance: [OWASP ASVS](https://owasp.org/www-project-application-security-verification-standard/), [OWASP Logging Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html), and [NIST SSDF SP 800-218](https://csrc.nist.gov/pubs/sp/800/218/final).
