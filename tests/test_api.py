import http.client
import json
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path

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


if __name__ == "__main__":
    unittest.main()
