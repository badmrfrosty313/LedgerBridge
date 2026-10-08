import csv
import io
import json
import tempfile
import unittest
from pathlib import Path

from ledgerbridge.core import Store, WorkflowError, money
from ledgerbridge.extraction.parser import parse_document


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.temp.name) / "test.sqlite3")

    def tearDown(self):
        self.temp.cleanup()

    def add(self, number="INV-1", text=None):
        text = text or f"EXAMPLE SERVICES LLC\nInvoice # {number}\nInvoice Date 10/01/2026\nSubtotal 100.00\nTax 7.00\nTotal Due 107.00"
        doc_id = self.store.import_text(text, "sample.txt", "Tester")[0]["id"]
        return self.store.detail(doc_id)

    def code(self, doc):
        return self.store.edit(doc["id"], {"account_code": "5100", "department": "Operations"}, doc["revision"], "Tester")

    def approve(self, doc):
        return self.store.transition(doc["id"], "approve", doc["revision"], "Reviewer")

    def test_complete_workflow_persists_immutable_export(self):
        doc = self.add()
        self.assertIn("missing_account_code", [i["code"] for i in doc["issues"]])
        with self.assertRaises(WorkflowError):
            self.approve(doc)
        doc = self.code(doc)
        self.assertTrue(doc["ready"])
        doc = self.approve(doc)
        exported = self.store.export("Reviewer")
        content = self.store.export_content(exported["id"])
        rows = list(csv.DictReader(io.StringIO(content)))
        self.assertEqual(rows[0]["total"], "107.00")
        self.assertEqual(rows[0]["account_code"], "5100")
        restarted = Store(self.store.path)
        self.assertEqual(restarted.detail(doc["id"])["status"], "exported")
        self.assertEqual(restarted.export_content(exported["id"]), content)
        with self.assertRaises(WorkflowError):
            self.store.edit(doc["id"], {"total_cents": 5}, doc["revision"] + 1, "Tester")
        with self.assertRaises(WorkflowError):
            self.store.export("Reviewer")

    def test_idempotent_import(self):
        first = self.add()
        second = self.add()
        self.assertEqual(first["id"], second["id"])
        self.assertEqual(len(self.store.list_documents()), 1)

    def test_changed_duplicate_invalidates_approval_and_reject_resolves(self):
        original = self.approve(self.code(self.add()))
        duplicate = self.add(text="EXAMPLE SERVICES LLC\nInvoice # INV-1\nInvoice Date 10/01/2026\nTotal Due 107.00\nAdditional copy")
        original = self.store.detail(original["id"])
        self.assertEqual(original["status"], "draft")
        self.assertTrue(any(i["code"] == "duplicate" for i in original["issues"]))
        self.store.transition(duplicate["id"], "reject", duplicate["revision"], "Tester", "Duplicate copy")
        self.assertTrue(self.store.detail(original["id"])["ready"])
        self.approve(self.store.detail(original["id"]))

    def test_exported_document_blocks_later_duplicate(self):
        original = self.approve(self.code(self.add()))
        self.store.export("Reviewer")
        duplicate = self.code(self.add(text="EXAMPLE SERVICES LLC\nInvoice # INV-1\nInvoice Date 10/01/2026\nTotal Due 107.00"))
        self.assertTrue(any(i["code"] == "duplicate" for i in duplicate["issues"]))
        self.assertEqual(self.store.detail(original["id"])["status"], "exported")
        with self.assertRaises(WorkflowError):
            self.approve(duplicate)

    def test_stale_edit_and_approval_are_rejected(self):
        old = self.add()
        current = self.code(old)
        for action in (lambda: self.store.edit(old["id"], {"vendor": "Wrong"}, old["revision"], "Tester"), lambda: self.approve(old)):
            with self.assertRaises(WorkflowError) as caught:
                action()
            self.assertEqual(caught.exception.status, 409)
        self.assertEqual(self.store.detail(old["id"])["revision"], current["revision"])

    def test_editing_approved_record_clears_approval(self):
        doc = self.approve(self.code(self.add()))
        doc = self.store.edit(doc["id"], {"notes": "Corrected"}, doc["revision"], "Tester")
        self.assertEqual(doc["status"], "draft")
        self.assertEqual(doc["events"][0]["action"], "edited")

    def test_reconciliation_limit_and_invalid_code_block_approval(self):
        doc = self.add()
        doc = self.store.edit(doc["id"], {"account_code": "bad", "department": "bad", "total_cents": 1000001}, doc["revision"], "Tester")
        codes = {i["code"] for i in doc["issues"]}
        self.assertTrue({"invalid_account_code", "invalid_department", "approval_limit", "reconciliation"} <= codes)
        with self.assertRaises(WorkflowError):
            self.approve(doc)

    def test_rules_changes_require_new_approval_and_freeze_currency(self):
        doc = self.approve(self.code(self.add()))
        settings = self.store.rules()
        rules = settings["rules"] | {"organization": "Another Business"}
        self.store.update_rules(rules, settings["revision"], "Admin")
        self.assertEqual(self.store.detail(doc["id"])["status"], "draft")
        with self.assertRaises(WorkflowError):
            self.store.update_rules(rules | {"currency": "EUR"}, settings["revision"] + 1, "Admin")
        with self.assertRaises(WorkflowError):
            self.store.update_rules(rules, settings["revision"], "Admin")

    def test_csv_batch_rolls_back_on_invalid_row(self):
        text = "vendor,date,total,account_code\nVendor A,2026-10-01,100.00,5100\nVendor B,2026-02-30,200.00,5100\n"
        with self.assertRaises(WorkflowError):
            self.store.import_csv(text, "test.csv", "Tester")
        self.assertEqual(self.store.list_documents(), [])
        self.assertEqual(self.store.events(), [])

    def test_csv_formula_neutralization_and_decimal_precision(self):
        self.store.import_csv("vendor,date,total,account_code,notes\n=HYPERLINK(123),2026-10-01,0.29,5100,+CMD\n", "test.csv", "Tester")
        doc = self.store.list_documents()[0]
        self.assertEqual(doc["fields"]["total_cents"], 29)
        self.approve(doc)
        result = self.store.export("Reviewer")
        row = next(csv.DictReader(io.StringIO(self.store.export_content(result["id"]))))
        self.assertEqual(row["vendor"], "'=HYPERLINK(123)")
        self.assertEqual(row["notes"], "'+CMD")
        from ledgerbridge.core import csv_cell
        for value in ("\x00=CMD", "\t=CMD", "  @SUM(1)", "\r+CMD"):
            self.assertTrue(csv_cell(value).startswith("'"), value)
        for value in ("NaN", "Infinity", "0.001", "99999999999999999"):
            with self.assertRaises(WorkflowError):
                money(value)

    def test_invalid_actor_rolls_back_export(self):
        doc = self.approve(self.code(self.add()))
        with self.assertRaises(WorkflowError):
            self.store.export("")
        self.assertEqual(self.store.detail(doc["id"])["status"], "approved")
        self.assertEqual(self.store.exports(), [])

    def test_check_request_vendor_is_payee(self):
        doc = self.add(text="TEST ORGANIZATION\nCHECK REQUEST\nDate 10/01/2026\nPay To TEST PAYEE LLC\nTOTAL AMOUNT REQUESTED 95.00")
        self.assertEqual(doc["fields"]["vendor"], "TEST PAYEE LLC")

    def test_fixture_extraction_regression(self):
        corpus = json.loads((Path(__file__).parents[1] / "ledgerbridge/demo.json").read_text())
        for fixture in corpus["fixtures"]:
            with self.subTest(fixture=fixture["id"]):
                parsed = parse_document(fixture["lines"]).to_dict()
                self.assertEqual(parsed["document_type"], fixture["family"])
                for key, value in fixture["expected"].items():
                    self.assertEqual(parsed[key], value)

    def test_reject_requires_reason_and_reopen_rechecks_duplicates(self):
        doc = self.add()
        with self.assertRaises(WorkflowError):
            self.store.transition(doc["id"], "reject", doc["revision"], "Tester", "")
        doc = self.store.transition(doc["id"], "reject", doc["revision"], "Tester", "Not payable")
        doc = self.store.transition(doc["id"], "reopen", doc["revision"], "Tester")
        self.assertEqual(doc["status"], "draft")


if __name__ == "__main__":
    unittest.main()
