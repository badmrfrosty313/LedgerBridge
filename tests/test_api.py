import http.client
import base64
import io
import json
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from openpyxl import Workbook

from ledgerbridge.core import Store
from ledgerbridge.server import handler_for


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), handler_for(Store(Path(self.temp.name) / "db.sqlite3")))
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.temp.cleanup()

    def request(self, method, path, body=None, headers=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port)
        payload = None if body is None else json.dumps(body)
        connection.request(method, path, body=payload, headers={"Content-Type": "application/json"} | (headers or {}))
        response = connection.getresponse()
        result = response.status, dict(response.getheaders()), response.read()
        connection.close()
        return result

    def test_live_api_workflow(self):
        status, headers, body = self.request("GET", "/")
        self.assertEqual(status, 200)
        self.assertIn(b"LedgerBridge", body)
        self.assertIn("Content-Security-Policy", headers)
        status, _, body = self.request("POST", "/api/import/csv", {"text": "vendor,date,total,account_code\nACME,2026-10-01,42.00,5100", "actor": "Tester"})
        self.assertEqual(status, 201)
        doc_id = json.loads(body)["records"][0]["id"]
        _, _, body = self.request("GET", "/api/documents/" + doc_id)
        doc = json.loads(body)
        status, _, _ = self.request("POST", f"/api/documents/{doc_id}/approve", {"revision": doc["revision"], "actor": "Tester"})
        self.assertEqual(status, 200)
        status, _, body = self.request("POST", "/api/exports", {"actor": "Tester"})
        self.assertEqual(status, 201)
        url = json.loads(body)["download_url"]
        status, headers, body = self.request("GET", url)
        self.assertEqual(status, 200)
        self.assertIn("attachment", headers["Content-Disposition"])
        self.assertIn(b"42.00", body)

    def test_cross_origin_and_rebinding_rejected(self):
        for headers in ({"Origin": "https://evil.example"}, {"Host": "evil.example"}, {"Sec-Fetch-Site": "cross-site"}):
            status, _, _ = self.request("POST", "/api/demo", {"actor": "Tester"}, headers)
            self.assertEqual(status, 403)

    def test_bad_payload_is_useful_client_error(self):
        for body in ([], {"text": None, "actor": "Tester"}):
            status, _, data = self.request("POST", "/api/import/text", body)
            self.assertEqual(status, 400)
            self.assertIn("error", json.loads(data))
        status, _, _ = self.request("GET", "/../../etc/passwd")
        self.assertEqual(status, 404)

    def test_excel_preview_requires_confirmation_before_creating_drafts(self):
        book = Workbook(); sheet = book.active
        sheet.append(["vendor", "date", "total", "account_code"])
        sheet.append(["SYNTHETIC EXCEL SUPPLIES", "2026-10-01", "42.00", "5100"])
        output = io.BytesIO(); book.save(output)
        payload = {"content_base64": base64.b64encode(output.getvalue()).decode(), "source_name": "synthetic.xlsx", "actor": "Tester"}
        status, _, body = self.request("POST", "/api/import/xlsx/preview", payload)
        self.assertEqual(status, 200)
        preview = json.loads(body)
        self.assertTrue(preview["valid"])
        self.assertEqual(json.loads(self.request("GET", "/api/documents")[2])["documents"], [])
        status, _, body = self.request("POST", "/api/import/xlsx/confirm", {"preview_token": preview["preview_token"], "actor": "Tester"})
        self.assertEqual(status, 201)
        self.assertEqual(len(json.loads(body)["records"]), 1)

    def test_excel_preview_rejects_malformed_base64_and_confirmation_is_single_use_under_race(self):
        for encoded in ("%%%", "YWJj$", ""):
            status, _, body = self.request("POST", "/api/import/xlsx/preview", {"content_base64": encoded, "source_name": "synthetic.xlsx", "actor": "Tester"})
            self.assertEqual(status, 400)
            self.assertIn("error", json.loads(body))
        book=Workbook(); sheet=book.active
        sheet.append(["vendor", "date", "total", "account_code"])
        sheet.append(["SYNTHETIC RACE", "2026-10-01", "8.25", "5100"])
        output=io.BytesIO(); book.save(output)
        status, _, body=self.request("POST", "/api/import/xlsx/preview", {"content_base64":base64.b64encode(output.getvalue()).decode(),"source_name":"synthetic.xlsx","actor":"Tester"})
        self.assertEqual(status,200); token=json.loads(body)["preview_token"]
        barrier=threading.Barrier(2); outcomes=[]
        def confirm():
            barrier.wait()
            outcomes.append(self.request("POST","/api/import/xlsx/confirm",{"preview_token":token,"actor":"Tester"})[0])
        threads=[threading.Thread(target=confirm) for _ in range(2)]
        for thread in threads: thread.start()
        for thread in threads: thread.join()
        self.assertCountEqual(outcomes,[201,409])
        self.assertEqual(len(json.loads(self.request("GET","/api/documents")[2])["documents"]),1)

    def test_allocation_preview_and_confirm_require_a_current_revision(self):
        status, _, body = self.request("POST", "/api/import/csv", {"text": "vendor,date,total,account_code\nSYNTHETIC,2026-10-01,0.01,5100", "actor": "Tester"})
        document_id = json.loads(body)["records"][0]["id"]
        status, _, body = self.request("POST", f"/api/documents/{document_id}/allocations/preview", {"items": [{"destination":"Fund A","percent":"50"},{"destination":"Fund B","percent":"50"}], "actor":"Tester"})
        self.assertEqual(status, 200); self.assertEqual(sum(item["cents"] for item in json.loads(body)["items"]), 1)
        revision = json.loads(self.request("GET", "/api/documents/" + document_id)[2])["revision"]
        status, _, body = self.request("POST", f"/api/documents/{document_id}/allocations/confirm", {"items": [{"destination":"Fund A","percent":"50"},{"destination":"Fund B","percent":"50"}], "revision": revision, "actor":"Tester"})
        self.assertEqual(status, 200); self.assertEqual(len(json.loads(body)["allocations"]), 2)


if __name__ == "__main__":
    unittest.main()
