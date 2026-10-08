"""Loopback connector for the separate demonstration ERP."""
import csv
import hashlib
import io
import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .core import WorkflowError, now


class DemoBridge:
    def __init__(self, store, port=8766):
        if not 1 <= port <= 65535:
            raise ValueError("Invalid demo ERP port")
        self.store = store
        self.origin = f"http://127.0.0.1:{port}"
        with store.connect(write=True) as db:
            db.execute("CREATE TABLE IF NOT EXISTS deliveries (export_id TEXT PRIMARY KEY, receipt TEXT NOT NULL, created_at TEXT NOT NULL)")

    def request(self, path, body=None):
        payload = None if body is None else json.dumps(body).encode()
        request = Request(self.origin + path, data=payload, headers={"Content-Type": "application/json"}, method="GET" if body is None else "POST")
        try:
            with urlopen(request, timeout=5) as response:
                data = response.read(2 * 1024 * 1024 + 1)
                if len(data) > 2 * 1024 * 1024:
                    raise WorkflowError("Demo ERP response exceeded the connector limit.", 502)
                result = json.loads(data)
                if not isinstance(result, dict):
                    raise ValueError("Response must be an object")
                return result
        except HTTPError as exc:
            raise WorkflowError(f"Demo ERP rejected the batch (HTTP {exc.code}).", 502) from None
        except (URLError, TimeoutError, OSError):
            raise WorkflowError("Demo ERP is unavailable. Start it with: python -m ledgerbridge.mock_erp", 503) from None
        except (ValueError, UnicodeError):
            raise WorkflowError("Demo ERP returned an invalid response.", 502) from None

    def status(self):
        try:
            return {"connected": True, "erp": self.request("/api/health")}
        except WorkflowError:
            return {"connected": False}

    def send(self, export_id, actor):
        if not isinstance(actor, str) or not actor.strip() or len(actor) > 120:
            raise WorkflowError("A reviewer name is required.")
        content = self.store.export_content(export_id)
        rows = list(csv.DictReader(io.StringIO(content)))
        digest = hashlib.sha256(json.dumps(rows, sort_keys=True).encode()).hexdigest()
        receipt = self.request("/api/batches", {"batch_id": export_id, "records": rows})
        if receipt.get("batch_id") != export_id or receipt.get("record_count") != len(rows) or receipt.get("payload_hash") != digest or not isinstance(receipt.get("receipt_id"), str):
            raise WorkflowError("Demo ERP receipt did not reconcile with the export. Retry after checking the target.", 502)
        with self.store.connect(write=True) as db:
            existing = db.execute("SELECT receipt FROM deliveries WHERE export_id=?", (export_id,)).fetchone()
            if existing:
                if json.loads(existing["receipt"])["receipt_id"] != receipt["receipt_id"]:
                    raise WorkflowError("Target receipt changed. The demo ERP database may have been reset.", 409)
            else:
                db.execute("INSERT INTO deliveries VALUES (?,?,?)", (export_id, json.dumps(receipt), now()))
                self.store.audit(db, None, "demo_erp_delivered", actor, {"export_id": export_id, "receipt": receipt})
        return receipt

    def deliveries(self):
        with self.store.connect() as db:
            return [{"export_id": row["export_id"], "receipt": json.loads(row["receipt"]), "created_at": row["created_at"]} for row in db.execute("SELECT * FROM deliveries ORDER BY created_at DESC")]
