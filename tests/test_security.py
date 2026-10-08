import io
import json
import sqlite3
import tempfile
import time
import unittest
from pathlib import Path

from ledgerbridge.auth import Auth
from ledgerbridge.core import Store, WorkflowError
from ledgerbridge.maintenance import backup_database
from ledgerbridge.wsgi import application_for


def request(app, method, path, body=None, cookie=None, csrf=None, origin="https://ledger.example", host="ledger.example"):
    payload = json.dumps(body).encode() if body is not None else b""
    environ = {
        "REQUEST_METHOD": method, "PATH_INFO": path,
        "QUERY_STRING": "", "wsgi.input": io.BytesIO(payload),
        "CONTENT_LENGTH": str(len(payload)), "CONTENT_TYPE": "application/json" if body is not None else "",
        "HTTP_HOST": host, "HTTP_ORIGIN": origin,
    }
    if cookie: environ["HTTP_COOKIE"] = cookie
    if csrf: environ["HTTP_X_CSRF_TOKEN"] = csrf
    result = {}
    def start(status, headers):
        result["status"] = int(status.split()[0]); result["headers"] = dict(headers)
    result["body"] = b"".join(app(environ, start))
    return result


class SecurityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "finance.sqlite3"
        self.store = Store(self.path)
        self.auth = Auth(self.store)
        self.auth.add_user("admin", "ThisIsAnExamplePasswordForTests2026!", "admin")
        self.auth.add_user("viewer", "AnotherExamplePasswordForTests2026!", "viewer")
        self.app = application_for(self.store, self.auth, "https://ledger.example")

    def tearDown(self):
        self.temp.cleanup()

    def login(self, user, password):
        result = request(self.app, "POST", "/api/login", {"username": user, "password": password})
        self.assertEqual(result["status"], 200)
        self.assertTrue(result["headers"]["Set-Cookie"].endswith("; Secure"))
        self.assertIn("HttpOnly; SameSite=Strict", result["headers"]["Set-Cookie"])
        cookie = result["headers"]["Set-Cookie"].split(";", 1)[0]
        identity = request(self.app, "GET", "/api/session", cookie=cookie)
        self.assertEqual(identity["status"], 200)
        return cookie, json.loads(identity["body"])["csrf"]

    def test_https_session_csrf_roles_and_server_owned_actor(self):
        self.assertEqual(request(self.app, "GET", "/api/documents")["status"], 401)
        self.assertEqual(request(self.app, "GET", "/")["status"], 303)
        admin_cookie, csrf = self.login("admin", "ThisIsAnExamplePasswordForTests2026!")
        self.assertIn("__Host-LedgerBridge=", admin_cookie)
        headers = request(self.app, "GET", "/api/session", cookie=admin_cookie)["headers"]
        self.assertIn("Strict-Transport-Security", headers)
        self.assertEqual(request(self.app, "POST", "/api/import/csv", {"text": "a", "actor": "forged"}, cookie=admin_cookie)["status"], 403)
        self.assertEqual(request(self.app, "POST", "/api/import/csv", {"text": "a"}, cookie=admin_cookie, csrf=csrf, origin="https://evil.example")["status"], 403)
        self.assertEqual(request(self.app, "GET", "/api/documents", cookie=admin_cookie, host="evil.example")["status"], 403)
        imported = request(self.app, "POST", "/api/import/csv", {"text": "vendor,date,total,account_code\nAcme,2026-10-01,42.00,5100", "actor": "forged"}, cookie=admin_cookie, csrf=csrf)
        self.assertEqual(imported["status"], 201)
        doc_id = json.loads(imported["body"])["records"][0]["id"]
        self.assertEqual(self.store.detail(doc_id)["events"][0]["actor"], "admin")
        viewer_cookie, viewer_csrf = self.login("viewer", "AnotherExamplePasswordForTests2026!")
        self.assertEqual(request(self.app, "GET", "/api/documents", cookie=viewer_cookie)["status"], 200)
        denied = request(self.app, "POST", f"/api/documents/{doc_id}/approve", {"revision": 1}, cookie=viewer_cookie, csrf=viewer_csrf)
        self.assertEqual(denied["status"], 403)
        self.assertEqual(request(self.app, "POST", "/api/exports", {}, cookie=viewer_cookie, csrf=viewer_csrf)["status"], 403)
        self.assertEqual(request(self.app, "POST", "/api/demo", {}, cookie=admin_cookie, csrf=csrf)["status"], 404)
        logout = request(self.app, "POST", "/api/logout", {}, cookie=viewer_cookie, csrf=viewer_csrf)
        self.assertEqual(logout["status"], 200)
        self.assertEqual(request(self.app, "GET", "/api/documents", cookie=viewer_cookie)["status"], 401)

    def test_login_lockout_password_reset_and_session_revocation(self):
        for _ in range(5):
            self.assertEqual(request(self.app, "POST", "/api/login", {"username": "viewer", "password": "bad"})["status"], 401)
        self.assertEqual(request(self.app, "POST", "/api/login", {"username": "viewer", "password": "AnotherExamplePasswordForTests2026!"})["status"], 401)
        self.auth.change_password("viewer", "ResetPasswordForTests2026!")
        cookie, _ = self.login("viewer", "ResetPasswordForTests2026!")
        self.auth.set_active("viewer", False)
        self.assertEqual(request(self.app, "GET", "/api/documents", cookie=cookie)["status"], 401)
        with self.assertRaises(WorkflowError):
            self.auth.set_active("admin", False)

    def test_independent_approval_blocks_contributors(self):
        self.auth.add_user("reviewer-two", "ReviewerPasswordForTests2026!", "reviewer")
        admin_cookie, admin_csrf = self.login("admin", "ThisIsAnExamplePasswordForTests2026!")
        imported = request(self.app, "POST", "/api/import/csv", {"text": "vendor,date,total,account_code\nAcme,2026-10-01,42.00,5100"}, cookie=admin_cookie, csrf=admin_csrf)
        doc_id = json.loads(imported["body"])["records"][0]["id"]
        denied = request(self.app, "POST", f"/api/documents/{doc_id}/approve", {"revision": 1}, cookie=admin_cookie, csrf=admin_csrf)
        self.assertEqual(denied["status"], 409)
        reviewer_cookie, reviewer_csrf = self.login("reviewer-two", "ReviewerPasswordForTests2026!")
        approved = request(self.app, "POST", f"/api/documents/{doc_id}/approve", {"revision": 1}, cookie=reviewer_cookie, csrf=reviewer_csrf)
        self.assertEqual(approved["status"], 200)
        self.assertEqual(self.store.detail(doc_id)["events"][0]["actor"], "reviewer-two")

    def test_session_expires_and_raw_token_is_never_stored(self):
        cookie, _ = self.login("admin", "ThisIsAnExamplePasswordForTests2026!")
        token = cookie.split("=", 1)[1]
        with self.store.connect(write=True) as db:
            stored = db.execute("SELECT token_hash FROM sessions").fetchone()[0]
            self.assertNotEqual(stored, token)
            db.execute("UPDATE sessions SET expires_at=?", (int(time.time()) - 1,))
        self.assertEqual(request(self.app, "GET", "/api/documents", cookie=cookie)["status"], 401)

    def test_backup_restores_records_and_roles_from_wal_snapshot(self):
        doc_id = self.store.import_csv("vendor,date,total,account_code\nAcme,2026-10-01,42.00,5100", "demo", "admin")[0]["id"]
        destination = Path(self.temp.name) / "backups" / "snapshot.sqlite3"
        backup_database(self.path, destination)
        restored = Store(destination)
        self.assertEqual(restored.detail(doc_id)["fields"]["total_cents"], 4200)
        self.assertTrue(Auth(restored).has_users())
        with self.assertRaises(ValueError):
            backup_database(self.path, destination)
        with sqlite3.connect(destination) as db:
            self.assertEqual(db.execute("PRAGMA integrity_check").fetchone()[0], "ok")

    def test_old_database_auto_backup_before_schema_upgrade(self):
        with sqlite3.connect(self.path) as db:
            db.execute("PRAGMA user_version=0")
        migrated = Store(self.path)
        self.assertEqual(migrated.rules()["revision"], 1)
        self.assertEqual(len(list(self.path.parent.glob("*.pre-v2-*.bak"))), 1)


if __name__ == "__main__":
    unittest.main()
