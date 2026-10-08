"""Independent fake ERP: accepts idempotent financial import batches."""
import argparse
import hashlib
import json
import re
import sqlite3
import uuid
from datetime import date
from http.server import ThreadingHTTPServer
from pathlib import Path

from .core import Store, WorkflowError, money, now
from .server import handler_for


class MockERP:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.store = Store.__new__(Store)
        self.store.path = self.path
        with self.store.connect(write=True) as db:
            db.execute("CREATE TABLE IF NOT EXISTS batches (batch_id TEXT PRIMARY KEY, receipt_id TEXT NOT NULL, payload_hash TEXT NOT NULL, record_count INTEGER NOT NULL, created_at TEXT NOT NULL)")
            db.execute("CREATE TABLE IF NOT EXISTS ledger (record_id TEXT PRIMARY KEY, batch_id TEXT NOT NULL, vendor TEXT NOT NULL, date TEXT NOT NULL, total_cents INTEGER NOT NULL, currency TEXT NOT NULL, account_code TEXT NOT NULL, source TEXT NOT NULL)")

    def accept(self, payload):
        if not isinstance(payload, dict) or not re.fullmatch(r"[a-f0-9]{32}", str(payload.get("batch_id", ""))):
            raise WorkflowError("A valid export batch ID is required.")
        batch_id = payload["batch_id"]
        records = payload.get("records")
        if not isinstance(records, list) or not 1 <= len(records) <= 5000 or any(not isinstance(row, dict) for row in records):
            raise WorkflowError("Batch must contain between 1 and 5000 records.")
        digest = hashlib.sha256(json.dumps(records, sort_keys=True).encode()).hexdigest()
        with self.store.connect(write=True) as db:
            previous = db.execute("SELECT * FROM batches WHERE batch_id=?", (batch_id,)).fetchone()
            if previous:
                if previous["payload_hash"] != digest:
                    raise WorkflowError("Batch ID already exists with different contents.", 409)
                return dict(previous) | {"replayed": True}
            for row in records:
                required = ("record_id", "vendor", "date", "total", "currency", "account_code")
                if any(not isinstance(row.get(key), str) or not row[key].strip() for key in required):
                    raise WorkflowError("A record is missing required ledger fields.")
                if not re.fullmatch(r"[a-f0-9]{32}", row["record_id"]) or not re.fullmatch(r"[A-Z]{3}", row["currency"]):
                    raise WorkflowError("Invalid record identifier or currency.")
                try:
                    if date.fromisoformat(row["date"]).isoformat() != row["date"]:
                        raise ValueError
                except ValueError:
                    raise WorkflowError("Invalid ledger date.") from None
                total = money(row["total"])
                if total <= 0:
                    raise WorkflowError("Ledger total must be positive.")
                try:
                    db.execute("INSERT INTO ledger VALUES (?,?,?,?,?,?,?,?)", (row["record_id"], batch_id, row["vendor"], row["date"], total, row["currency"], row["account_code"], json.dumps(row)))
                except sqlite3.IntegrityError:
                    raise WorkflowError("A record was already posted in another batch.", 409) from None
            receipt = {"batch_id": batch_id, "receipt_id": uuid.uuid4().hex, "payload_hash": digest, "record_count": len(records), "created_at": now()}
            db.execute("INSERT INTO batches VALUES (?,?,?,?,?)", tuple(receipt.values()))
        return receipt | {"replayed": False}

    def ledger(self):
        with self.store.connect() as db:
            return [dict(row) for row in db.execute("SELECT record_id,batch_id,vendor,date,total_cents,currency,account_code FROM ledger ORDER BY rowid DESC")]


def erp_handler(erp):
    class Handler(handler_for(None)):
        def dispatch(self):
            self.guard()
            path = self.path.split("?", 1)[0]
            if self.command == "GET" and path == "/api/health":
                return self.respond({"name": "LedgerBridge Demo ERP", "status": "ok", "ledger_count": len(erp.ledger())})
            if self.command == "GET" and path == "/api/ledger":
                return self.respond({"records": erp.ledger()})
            if self.command == "POST" and path == "/api/batches":
                return self.respond(erp.accept(self.body()), 201)
            raise WorkflowError("Route not found.", 404)
    return Handler


def main():
    parser = argparse.ArgumentParser(description="Run the separate simulated ERP")
    parser.add_argument("--port", type=int, default=8766)
    parser.add_argument("--db", default="data/demo-erp.sqlite3")
    args = parser.parse_args()
    server = ThreadingHTTPServer(("127.0.0.1", args.port), erp_handler(MockERP(args.db)))
    server.daemon_threads = True
    print(f"Demo ERP API is running at http://127.0.0.1:{server.server_port}/api/ledger", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
