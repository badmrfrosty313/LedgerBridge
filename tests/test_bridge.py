import csv
import io
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path

from ledgerbridge.bridge import DemoBridge
from ledgerbridge.core import Store, WorkflowError
from ledgerbridge.mock_erp import MockERP, erp_handler


class BridgeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.store = Store(root / "source.sqlite3")
        self.erp = MockERP(root / "target.sqlite3")
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), erp_handler(self.erp))
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.bridge = DemoBridge(self.store, self.server.server_port)
        doc_id = self.store.import_csv("vendor,date,total,account_code\nAcme Services,2026-10-01,107.00,5100", "demo.csv", "Tester")[0]["id"]
        doc = self.store.detail(doc_id)
        self.store.transition(doc_id, "approve", doc["revision"], "Reviewer")
        self.export = self.store.export("Reviewer")

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.temp.cleanup()

    def test_separate_erp_receipt_and_retry_do_not_double_post(self):
        receipt = self.bridge.send(self.export["id"], "Tester")
        retry = self.bridge.send(self.export["id"], "Tester")
        self.assertFalse(receipt["replayed"])
        self.assertTrue(retry["replayed"])
        self.assertEqual(receipt["receipt_id"], retry["receipt_id"])
        self.assertEqual(len(self.erp.ledger()), 1)
        self.assertEqual(self.erp.ledger()[0]["total_cents"], 10700)
        self.assertEqual(len(self.bridge.deliveries()), 1)
        self.assertEqual(len([e for e in self.store.events() if e["action"] == "demo_erp_delivered"]), 1)
        self.assertTrue(self.bridge.status()["connected"])

    def test_retry_recovers_when_local_receipt_was_not_saved(self):
        self.bridge.send(self.export["id"], "Tester")
        with self.store.connect(write=True) as db:
            db.execute("DELETE FROM deliveries")
        receipt = self.bridge.send(self.export["id"], "Tester")
        self.assertTrue(receipt["replayed"])
        self.assertEqual(len(self.erp.ledger()), 1)
        self.assertEqual(len(self.bridge.deliveries()), 1)

    def test_erp_conflicting_batch_and_record_ids_rejected(self):
        self.bridge.send(self.export["id"], "Tester")
        rows = list(csv.DictReader(io.StringIO(self.store.export_content(self.export["id"]))))
        rows[0]["total"] = "108.00"
        with self.assertRaises(WorkflowError) as caught:
            self.erp.accept({"batch_id": self.export["id"], "records": rows})
        self.assertEqual(caught.exception.status, 409)
        with self.assertRaises(WorkflowError):
            self.erp.accept({"batch_id": "a" * 32, "records": rows})
        self.assertEqual(len(self.erp.ledger()), 1)

    def test_target_batch_validation_is_atomic(self):
        rows = list(csv.DictReader(io.StringIO(self.store.export_content(self.export["id"]))))
        rows.append(rows[0] | {"record_id": "b" * 32, "date": "bad date"})
        with self.assertRaises(WorkflowError):
            self.erp.accept({"batch_id": self.export["id"], "records": rows})
        self.assertEqual(self.erp.ledger(), [])

    def test_receipt_mismatch_is_not_recorded_as_delivered(self):
        self.bridge.request = lambda *args: {"batch_id": self.export["id"], "record_count": 99}
        with self.assertRaises(WorkflowError) as caught:
            self.bridge.send(self.export["id"], "Tester")
        self.assertEqual(caught.exception.status, 502)
        self.assertEqual(self.bridge.deliveries(), [])


if __name__ == "__main__":
    unittest.main()
