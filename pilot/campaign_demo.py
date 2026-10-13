"""Reproducible end-to-end LedgerBridge 2.0 synthetic benchmark."""
from __future__ import annotations

import io
import json
import tempfile
from pathlib import Path
from time import perf_counter

from openpyxl import Workbook

from ledgerbridge.bridge import DemoBridge
from ledgerbridge.core import Store
from ledgerbridge.excel import preview_xlsx
from ledgerbridge.mock_erp import MockERP


def run_demo():
    """Exercise preview -> draft -> allocation -> approval -> mapped receipt."""
    with tempfile.TemporaryDirectory(prefix="ledgerbridge-campaign-") as directory:
        root = Path(directory)
        store = Store(root / "source.sqlite3")
        started = perf_counter()

        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "Synthetic Invoice"
        sheet.append(["vendor", "document_number", "date", "total", "account_code", "department"])
        sheet.append(["SYNTHETIC NORTHSTAR SUPPLY", "SYN-2042", "2026-10-12", "100.01", "5100", "Operations"])
        content = io.BytesIO()
        workbook.save(content)
        preview = preview_xlsx(content.getvalue(), "synthetic-campaign.xlsx")
        assert len(store.list_documents()) == 0, "XLSX preview persisted a document"
        assert len(preview) == 1 and preview[0]["errors"] == [], preview

        row = preview[0]
        imported = store.import_records([{
            "fields": row["fields"], "source_name": "synthetic-campaign.xlsx · row 2",
            "raw_text": json.dumps(row["fields"], sort_keys=True), "document_type": "xlsx_row", "warnings": [],
        }], "Synthetic Intake")
        document_id = imported[0]["id"]
        document = store.detail(document_id)
        allocation = store.allocation_preview(document_id, [
            {"destination": "Fund A", "percent": "60"},
            {"destination": "Fund B", "percent": "40"},
        ])
        assert allocation["source_cents"] == 10001
        assert allocation["allocated_cents"] == 10001 and allocation["difference_cents"] == 0
        saved = store.save_allocations(document_id, allocation["items"], document["revision"], "Synthetic Allocator")
        approved = store.transition(document_id, "approve", saved["revision"], "Synthetic Approver", independent=True)
        assert approved["status"] == "approved"

        profile = store.mapping_profile()
        changed_profile = profile["profile"] | {
            "account_map": profile["profile"]["account_map"] | {"5100": "6100"},
            "expand_allocations": True,
        }
        store.save_mapping_profile(changed_profile, profile["revision"], "Synthetic Mapper")
        dry_run = store.mapping_dry_run()
        assert dry_run["rejected"] == []
        assert len(dry_run["rows"]) == 2
        assert dry_run["source_total_cents"] == dry_run["mapped_total_cents"] == 10001
        assert dry_run["difference_cents"] == 0
        exported = store.confirm_mapping_export(dry_run["preview_id"], dry_run["profile_revision"], "Synthetic Export Admin")

        target = MockERP(root / "target.sqlite3")
        bridge = DemoBridge(store)
        bridge.request = lambda path, body=None: target.accept(body) if path == "/api/batches" and body is not None else {"status": "ok"}
        receipt = bridge.send(exported["id"], "Synthetic Delivery Admin")
        replay = bridge.send(exported["id"], "Synthetic Delivery Admin")
        ledger = target.ledger()
        assert receipt["record_count"] == 2 and replay["receipt_id"] == receipt["receipt_id"]
        assert sum(item["total_cents"] for item in ledger) == 10001
        assert {item["account_code"] for item in ledger} == {"6100"}
        assert store.detail(document_id)["status"] == "exported"

        counted_actions = ("imported", "allocations_saved", "approve", "mapping_profile_updated",
                           "exported_mapped", "mapped_export_created", "demo_erp_delivered")
        with store.connect() as db:
            observed = {row["action"]: row["count"] for row in db.execute(
                "SELECT action,COUNT(*) AS count FROM events GROUP BY action"
            )}
            actor_count = db.execute("SELECT COUNT(DISTINCT actor) FROM events WHERE actor LIKE 'Synthetic %'").fetchone()[0]
        workflow_decision_events = sum(observed.get(action, 0) for action in counted_actions)
        elapsed_ms = round((perf_counter() - started) * 1000, 3)
        return {
            "label": "synthetic local benchmark; not a customer pilot or savings estimate",
            "elapsed_ms": elapsed_ms,
            "source_rows": 1,
            "allocation_rows": 2,
            "independent_approvals": 1,
            "export_rows": exported["record_count"],
            "synthetic_workflow_decision_events": workflow_decision_events,
            "synthetic_actor_count": actor_count,
            "source_total_cents": dry_run["source_total_cents"],
            "allocated_total_cents": allocation["allocated_cents"],
            "export_total_cents": dry_run["mapped_total_cents"],
            "simulated_erp_total_cents": sum(item["total_cents"] for item in ledger),
            "balance_difference_cents": dry_run["difference_cents"],
            "delivery_retry_replayed": replay["replayed"],
            "human_time_or_savings_claimed": False,
        }


if __name__ == "__main__":
    print(json.dumps(run_demo(), indent=2))
