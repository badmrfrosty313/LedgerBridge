"""Isolated, deterministic closed-pilot acceptance run. Uses only synthetic data."""
from __future__ import annotations

import argparse
import csv
import io
import json
import tempfile
from decimal import Decimal
from pathlib import Path

from ledgerbridge.auth import Auth
from ledgerbridge.core import Store, WorkflowError
from ledgerbridge.maintenance import backup_database

ROOT = Path(__file__).parent


def check(condition, message):
    if not condition:
        raise AssertionError(message)


def acceptance():
    fixture = (ROOT / "fixtures.csv").read_text(encoding="utf-8")
    expected = json.loads((ROOT / "expected.json").read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory(prefix="ledgerbridge-pilot-") as directory:
        path = Path(directory) / "pilot.sqlite3"
        store = Store(path)
        auth = Auth(store)
        auth.add_user("operator", "SyntheticPilotOperatorPassword!", "admin")
        auth.add_user("intake", "SyntheticPilotIntakePassword!", "reviewer")
        auth.add_user("approver", "SyntheticPilotApproverPassword!", "reviewer")
        bad_batch = fixture + "Invalid Date,BD-01,2026-02-30,1.00,0.00,1.00,5100,Operations,Bad row\n"
        try:
            store.import_csv(bad_batch, "bad-batch.csv", "intake")
            raise AssertionError("Invalid batch was accepted")
        except WorkflowError:
            pass
        check(not store.list_documents(), "Invalid batch did not roll back")

        imported = store.import_csv(fixture, "pilot-fixtures.csv", "intake")
        check(len(imported) == len(expected["issue_codes_by_row"]), "Fixture count changed")
        check(all(not record["existing"] for record in imported), "Unexpected existing record")
        ids = [record["id"] for record in imported]
        for index, doc_id in enumerate(ids):
            actual = sorted(issue["code"] for issue in store.detail(doc_id)["issues"])
            check(actual == sorted(expected["issue_codes_by_row"][index]), f"Issue mismatch at row {index}: {actual}")
        duplicate = store.import_csv(fixture, "pilot-fixtures.csv", "intake")
        check(all(record["existing"] for record in duplicate), "Exact reimport created new records")
        check(len(store.list_documents()) == len(ids), "Exact reimport changed record count")

        for index in expected["reject_rows"]:
            doc = store.detail(ids[index])
            store.transition(doc["id"], "reject", doc["revision"], "intake", "Pilot exception excluded")
        for index, fields in expected["corrections"].items():
            doc = store.detail(ids[int(index)])
            store.edit(doc["id"], fields, doc["revision"], "intake")

        approved = []
        for index, doc_id in enumerate(ids):
            doc = store.detail(doc_id)
            if index in expected["reject_rows"]:
                check(doc["status"] == "rejected", f"Rejected row {index} changed")
                continue
            check(doc["ready"], f"Row {index} has unresolved exceptions: {doc['issues']}")
            try:
                store.transition(doc_id, "approve", doc["revision"], "intake", independent=True)
                raise AssertionError("Importer approved their own record")
            except WorkflowError as exc:
                check(exc.status == 409, "Wrong independent approval result")
            approved.append(store.transition(doc_id, "approve", doc["revision"], "approver", independent=True))
        result = store.export("operator")
        check(result["record_count"] == expected["expected_export_count"], "Export count mismatch")
        content = store.export_content(result["id"])
        rows = list(csv.DictReader(io.StringIO(content)))
        check(sum(int(Decimal(row["total"]) * 100) for row in rows) == expected["expected_export_total_cents"], "Export total mismatch")
        check(any(row["vendor"].startswith("'=HYPERLINK") for row in rows), "Spreadsheet formula was not escaped")
        check(all(store.detail(doc["id"])["status"] == "exported" for doc in approved), "Export did not lock records")
        snapshot = Path(directory) / "backup.sqlite3"
        backup_database(path, snapshot)
        restored = Store(snapshot)
        check(restored.export_content(result["id"]) == content, "Restore lost immutable export")
        check(Auth(restored).has_users(), "Restore lost accounts")
        check(len(restored.list_documents()) == len(ids), "Restore lost records")
        return {"passed": True, "imported": len(ids), "approved_and_exported": len(rows),
                "rejected": len(expected["reject_rows"]), "export_total": f"{expected['expected_export_total_cents'] / 100:.2f}",
                "checks": ["atomic rollback", "issue detection", "idempotent reimport", "independent approval",
                           "correction and exclusion", "CSV formula escape", "export reconciliation", "backup restore"]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run isolated synthetic LedgerBridge pilot acceptance")
    parser.parse_args()
    print(json.dumps(acceptance(), indent=2))
