# Closed pilot kit

This kit uses invented vendors, amounts, account codes, and dates. It does not need a customer, credentials, or a live accounting system. It is a controlled test of the current review and CSV export workflow, not permission to post transactions.

## Automated acceptance

From the repository root, with Python 3.11+:

```sh
python -m pilot.run
```

The runner uses a temporary database that is deleted at completion. It verifies an invalid batch rolls back, 11 cases produce the expected exceptions, exact reimport is idempotent, three exceptions are rejected, four cases are corrected, a second person approves eight cases, the export reconciles to **$638.00**, formula text is escaped, records are locked after export, and a database snapshot restores. The `expected.json` file contains the expected issue codes and disposition for each zero-based CSV data row. A failed assertion returns a nonzero exit status.

## Human walkthrough

Use a fresh database. The following example is for a private loopback test; choose distinct passwords at each prompt. The global `--db` flag goes before the admin command.

```sh
python -m ledgerbridge.admin --db data/pilot.sqlite3 add-user pilot-admin --role admin
python -m ledgerbridge.admin --db data/pilot.sqlite3 add-user intake --role reviewer
python -m ledgerbridge.admin --db data/pilot.sqlite3 add-user approver --role reviewer
python -m ledgerbridge.server --local-auth --db data/pilot.sqlite3
```

1. Open `http://127.0.0.1:8765`. Sign in as **intake** and import `pilot/fixtures.csv`. Record how long the import and review take.
2. Check each row against `pilot/expected.json`. The clean records are ready; the wrong account, missing account, limit, mismatch, duplicate pair, credit, and missing payee need attention. Try approving one as intake and confirm the independent-review rule blocks it.
3. As intake, reject the limit case, second duplicate, and credit with reasons. Correct the other four exception rows per `expected.json`. Do not silently change an amount without checking the source document; this synthetic kit supplies ground truth.
4. Sign out; sign in as **approver** and inspect each record's source, corrections, and history before approving the eight ready rows.
5. Sign in as **pilot-admin**, create the export, and compare eight rows and the **$638.00** total with the fixtures. Confirm the formula-style vendor begins with a literal apostrophe in the CSV. Reimport the same CSV and verify no new documents appear. Save the CSV in an approved test location only.
6. Back up the database with `python -m ledgerbridge.maintenance backup --db data/pilot.sqlite3 --out data/pilot-backup.sqlite3`. Follow `docs/DEPLOYMENT.md` to practice restoring it into a separate test path. Do not overwrite the live pilot database during the exercise.

## Record the result

Copy `pilot/scorecard.csv` for each run and fill its blank `actual`, `pass`, and `notes` columns. A pass means all expected classifications, corrections, counts, totals, and access checks match. Log any wrong or missed case with its row number, source, expected behavior, and observed behavior. Stop the pilot on an unaccounted total, unexpected export, unauthorized approval, or failed restore.

This corpus tests supported flat CSV inputs. It cannot establish accuracy on new invoices, scanned images, Excel files, line items, credits, or a real target system. For an external company trial, obtain permitted representative samples, label expected values independently, define acceptance thresholds and allowed data handling up front, and run in parallel without live posting.
