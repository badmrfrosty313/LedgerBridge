"""Loopback connector for the separate demonstration ERP."""
import csv
import hashlib
import io
import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .core import WorkflowError, money, now


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
            if exc.code == 404:
                raise WorkflowError("Target batch receipt is missing; the simulated ERP may have been reset.", 409) from None
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

    def reconciliation(self):
        """Compare mapped source/export totals with the separate local target receipt."""
        with self.store.connect() as db:
            rows = db.execute("SELECT e.id,e.created_at,e.actor,e.content,m.profile_revision,m.profile_version,m.source_ids,m.source_total_cents,m.mapped_total_cents,m.content_hash,d.receipt FROM exports e JOIN mapping_export_meta m ON m.export_id=e.id LEFT JOIN deliveries d ON d.export_id=e.id ORDER BY e.created_at DESC").fetchall()
        result = []
        for row in rows:
            try:
                export_rows = list(csv.DictReader(io.StringIO(row["content"])))
                export_total = sum(money(item["total"]) for item in export_rows)
                export_hash = hashlib.sha256(row["content"].encode()).hexdigest()
            except (TypeError, ValueError, KeyError):
                export_rows, export_total, export_hash = [], None, None
            source_total = row["source_total_cents"]
            mapped_total = row["mapped_total_cents"]
            try:
                delivery = json.loads(row["receipt"]) if row["receipt"] else None
                if delivery is not None and not isinstance(delivery, dict): raise ValueError
            except (TypeError, ValueError):
                delivery = {"malformed": True}
            received = None
            state = "not_sent" if delivery is None else "receipt_mismatch" if delivery.get("malformed") else "target_unavailable"
            if type(source_total) is not int or type(mapped_total) is not int or export_hash != row["content_hash"] or export_total != mapped_total or source_total != mapped_total:
                state = "export_mismatch"
            elif delivery is not None and not delivery.get("malformed"):
                try:
                    target = self.request(f"/api/batches/{row['id']}")
                    received_value = target.get("received_total_cents")
                    if type(received_value) is int:
                        received = received_value
                    if (target.get("batch_id") == row["id"] == delivery.get("batch_id")
                            and isinstance(target.get("receipt_id"), str)
                            and target.get("receipt_id") == delivery.get("receipt_id")
                            and type(received_value) is int
                            and target.get("payload_hash") == delivery.get("payload_hash") == hashlib.sha256(json.dumps(export_rows, sort_keys=True).encode()).hexdigest()
                            and target.get("record_count") == target.get("received_row_count") == len(export_rows)
                            and received == export_total):
                        state = "reconciled"
                    else:
                        state = "receipt_mismatch"
                except WorkflowError as exc:
                    state = "receipt_mismatch" if exc.status in (404, 409) else "target_unavailable"
                except (KeyError, TypeError):
                    state = "receipt_mismatch"
            try:
                source_ids=json.loads(row["source_ids"])
                if not isinstance(source_ids,list) or any(not isinstance(value,str) for value in source_ids): raise ValueError
            except (TypeError, ValueError):
                source_ids=[]
                state="export_mismatch"
            result.append({
                "export_id": row["id"], "created_at": row["created_at"], "actor": row["actor"],
                "profile_revision": row["profile_revision"], "profile_version": row["profile_version"],
                "source_ids": source_ids, "row_count": len(export_rows),
                "source_total_cents": source_total, "mapped_total_cents": mapped_total,
                "export_total_cents": export_total, "received_total_cents": received,
                "source_mapping_difference_cents": source_total - mapped_total if type(source_total) is int and type(mapped_total) is int else None,
                "mapping_export_difference_cents": mapped_total - export_total if type(mapped_total) is int and type(export_total) is int else None,
                "export_received_difference_cents": export_total - received if type(export_total) is int and type(received) is int else None,
                "delivery_state": state,
            })
        return result
