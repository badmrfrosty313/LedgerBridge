# Attribution and dependencies

LedgerBridge's extraction parser and classifier were adapted from Kyle Hawkins's earlier [Invoice-to-Ledger-Automation](https://github.com/badmrfrosty313/Invoice-to-Ledger-Automation) prototype. They are included in this project's MIT grant. The shipped demo and pilot fixtures are invented examples; no original business documents are included.

Dependencies are installed separately and retain their own licenses. LedgerBridge's MIT license does not relicense those packages.

| Dependency | Purpose | License |
|---|---|---|
| [Waitress](https://github.com/Pylons/waitress) | Production WSGI server | Zope Public License 2.1 |
| [Playwright](https://github.com/microsoft/playwright) | Development browser checks | Apache License 2.0 |

Python, Node.js, browsers installed by Playwright, and GitHub Actions have their own licenses. Distributing those dependencies or a packaged runtime requires preserving their applicable notices.
