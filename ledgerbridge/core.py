from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import re
import sqlite3
import uuid
from contextlib import closing, contextmanager
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

from .extraction.parser import parse_document


class WorkflowError(ValueError):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


DEFAULT_RULES = {
    "organization": "Demo Business",
    "currency": "USD",
    "required_fields": ["vendor", "date", "total_cents", "account_code"],
    "account_codes": ["5100", "5200", "5300", "5400"],
    "departments": ["Operations", "Administration", "Technology"],
    "approval_limit_cents": 1000000,
    "reconciliation_tolerance_cents": 2,
}
FIELDS = {"vendor", "document_number", "date", "subtotal_cents", "tax_cents", "total_cents", "account_code", "department", "notes"}
MONEY_FIELDS = {"subtotal_cents", "tax_cents", "total_cents"}


def now():
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def money(value):
    """Parse decimal currency without silently rounding fractional cents."""
    if value is None or str(value).strip() == "":
        return None
    try:
        text = str(value).strip().replace(",", "").replace("$", "")
        if text.startswith("(") and text.endswith(")"):
            text = "-" + text[1:-1]
        number = Decimal(text) * 100
        if not number.is_finite() or number != number.to_integral_value():
            raise ValueError
        cents = int(number)
        if abs(cents) > 10**12:
            raise ValueError
        return cents
    except (InvalidOperation, ValueError):
        raise WorkflowError(f"Invalid currency amount: {value!r}") from None


def normalize_fields(fields):
    if not isinstance(fields, dict) or set(fields) - FIELDS:
        raise WorkflowError("Unknown or invalid document fields.")
    result = {}
    for key, value in fields.items():
        if key in MONEY_FIELDS:
            if value is not None and (type(value) is not int or abs(value) > 10**12):
                raise WorkflowError(f"{key} must be integer cents or null.")
        else:
            if value is not None and (not isinstance(value, str) or len(value) > 2000):
                raise WorkflowError(f"{key} must be text (maximum 2000 characters).")
            value = value.strip() if isinstance(value, str) else value
            if key == "date" and value:
                try:
                    if date.fromisoformat(value).isoformat() != value:
                        raise ValueError
                except ValueError:
                    raise WorkflowError("Date must be a valid YYYY-MM-DD date.") from None
        result[key] = value
    return result


def validate_rules(rules):
    if not isinstance(rules, dict) or set(rules) != set(DEFAULT_RULES):
        raise WorkflowError("Rules must include exactly the documented configuration fields.")
    if not isinstance(rules["organization"], str) or not 1 <= len(rules["organization"].strip()) <= 120:
        raise WorkflowError("Organization name is required (maximum 120 characters).")
    if not isinstance(rules["currency"], str) or not re.fullmatch(r"[A-Z]{3}", rules["currency"]):
        raise WorkflowError("Currency must be a three-letter uppercase code.")
    for key in ("required_fields", "account_codes", "departments"):
        items = rules[key]
        if not isinstance(items, list) or len(items) > 100 or any(not isinstance(v, str) or not v.strip() or len(v) > 120 for v in items) or len(set(items)) != len(items):
            raise WorkflowError(f"Invalid {key} list.")
    if set(rules["required_fields"]) - FIELDS or not {"vendor", "date", "total_cents"} <= set(rules["required_fields"]):
        raise WorkflowError("Required fields must include vendor, date, total_cents and use supported field names.")
    for key in ("approval_limit_cents", "reconciliation_tolerance_cents"):
        if type(rules[key]) is not int or not 0 <= rules[key] <= 10**12:
            raise WorkflowError(f"Invalid {key}.")
    return rules


def csv_cell(value):
    # Quoted CSV alone does not prevent spreadsheet formula execution.
    text = "" if value is None else str(value)
    # Some spreadsheet readers ignore leading whitespace or NUL bytes.
    leading = text.lstrip()
    if leading.startswith(("=", "+", "-", "@", "\x00")) or text.startswith(("\t", "\r", "\n", "\x00")):
        return "'" + text
    return text


class Store:
    def __init__(self, path):
        self.path = Path(path)
        if not self.path.parent.exists():
            self.path.parent.mkdir(parents=True, mode=0o700)
        if self.path.exists():
            with closing(sqlite3.connect(self.path)) as previous:
                version = previous.execute("PRAGMA user_version").fetchone()[0]
                if version > 2:
                    raise WorkflowError("Database was created by a newer LedgerBridge version.")
                old_schema = previous.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='documents'").fetchone()
                if version == 0 and old_schema:
                    from .maintenance import backup_database
                    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
                    backup_database(self.path, self.path.with_name(f"{self.path.name}.pre-v2-{stamp}.bak"))
        with self.connect() as db:
            db.executescript("""
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS settings (id INTEGER PRIMARY KEY CHECK(id=1), rules TEXT NOT NULL, revision INTEGER NOT NULL);
                CREATE TABLE IF NOT EXISTS documents (
                    id TEXT PRIMARY KEY, source_name TEXT NOT NULL, source_hash TEXT UNIQUE NOT NULL,
                    raw_text TEXT NOT NULL, fields TEXT NOT NULL, document_type TEXT NOT NULL,
                    extraction_warnings TEXT NOT NULL, status TEXT NOT NULL, revision INTEGER NOT NULL,
                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL, export_id TEXT
                );
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, document_id TEXT, action TEXT NOT NULL,
                    actor TEXT NOT NULL, detail TEXT NOT NULL, created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS exports (id TEXT PRIMARY KEY, content TEXT NOT NULL, created_at TEXT NOT NULL, actor TEXT NOT NULL);
            """)
            db.execute("INSERT OR IGNORE INTO settings VALUES (1, ?, 1)", (json.dumps(DEFAULT_RULES),))
            if db.execute("PRAGMA user_version").fetchone()[0] == 0:
                db.execute("PRAGMA user_version=1")
        if os.name == "posix" and self.path.exists():
            os.chmod(self.path, 0o600)

    @contextmanager
    def connect(self, write=False):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        try:
            if write:
                db.execute("BEGIN IMMEDIATE")
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def audit(self, db, document_id, action, actor, detail):
        if not isinstance(actor, str) or not actor.strip() or len(actor) > 120:
            raise WorkflowError("A reviewer name is required (maximum 120 characters).")
        db.execute("INSERT INTO events(document_id,action,actor,detail,created_at) VALUES (?,?,?,?,?)",
                   (document_id, action, actor.strip(), json.dumps(detail), now()))

    def rules(self, db=None):
        if db is None:
            with self.connect() as db:
                return self.rules(db)
        row = db.execute("SELECT * FROM settings WHERE id=1").fetchone()
        return {"rules": json.loads(row["rules"]), "revision": row["revision"]}

    def get(self, db, document_id):
        row = db.execute("SELECT * FROM documents WHERE id=?", (document_id,)).fetchone()
        if row is None:
            raise WorkflowError("Document not found.", 404)
        return row

    def issues(self, db, row, rules=None):
        fields = json.loads(row["fields"])
        rules = rules or self.rules(db)["rules"]
        issues = []
        def add(code, message):
            issues.append({"code": code, "message": message})
        for key in rules["required_fields"]:
            if fields.get(key) is None or fields.get(key) == "":
                add("missing_" + key, f"Required field missing: {key.replace('_cents', '').replace('_', ' ')}.")
        if fields.get("total_cents") is not None:
            if fields["total_cents"] <= 0:
                add("nonpositive_total", "Total must be greater than zero. Credit notes need a separate workflow.")
            if fields["total_cents"] > rules["approval_limit_cents"]:
                add("approval_limit", "Amount exceeds the configured approval limit.")
        if all(fields.get(k) is not None for k in MONEY_FIELDS):
            if abs(fields["subtotal_cents"] + fields["tax_cents"] - fields["total_cents"]) > rules["reconciliation_tolerance_cents"]:
                add("reconciliation", "Subtotal + tax does not match total. Resolve or correct the component amounts.")
        for key, config in (("account_code", "account_codes"), ("department", "departments")):
            if fields.get(key) and rules[config] and fields[key] not in rules[config]:
                add("invalid_" + key, f"{key.replace('_', ' ').title()} is not in the configured list.")
        vendor = (fields.get("vendor") or "").strip().casefold()
        number = (fields.get("document_number") or "").strip().casefold()
        if vendor:
            for other in db.execute("SELECT id, fields FROM documents WHERE id != ? AND status != 'rejected'", (row["id"],)):
                peer = json.loads(other["fields"])
                if (peer.get("vendor") or "").strip().casefold() != vendor:
                    continue
                same_number = number and number == (peer.get("document_number") or "").strip().casefold()
                same_payment = not number and not peer.get("document_number") and fields.get("date") and fields.get("date") == peer.get("date") and fields.get("total_cents") is not None and fields.get("total_cents") == peer.get("total_cents")
                if same_number or same_payment:
                    add("duplicate", "Potential duplicate of " + other["id"][:8] + ". Reject the redundant record before approval/export.")
        return issues

    def document(self, db, row):
        result = dict(row)
        for key in ("fields", "extraction_warnings"):
            result[key] = json.loads(result[key])
        result["issues"] = self.issues(db, row) if row["status"] != "exported" else []
        result["ready"] = not result["issues"] and row["status"] == "draft"
        return result

    def list_documents(self):
        with self.connect() as db:
            return [self.document(db, row) for row in db.execute("SELECT * FROM documents ORDER BY created_at DESC")]

    def detail(self, document_id):
        with self.connect() as db:
            result = self.document(db, self.get(db, document_id))
            result["events"] = [dict(row) | {"detail": json.loads(row["detail"])} for row in db.execute("SELECT * FROM events WHERE document_id=? ORDER BY id DESC", (document_id,))]
            return result

    def invalidate_approvals(self, db):
        for row in db.execute("SELECT * FROM documents WHERE status='approved'").fetchall():
            issues = self.issues(db, row)
            if issues:
                db.execute("UPDATE documents SET status='draft', revision=revision+1, updated_at=? WHERE id=?", (now(), row["id"]))
                self.audit(db, row["id"], "approval_invalidated", "system", {"issues": issues})

    def import_records(self, records, actor):
        if not isinstance(records, list) or not 1 <= len(records) <= 500:
            raise WorkflowError("Import between 1 and 500 records.")
        result = []
        with self.connect(write=True) as db:
            for record in records:
                fields = normalize_fields(record["fields"])
                raw = record.get("raw_text", "")
                source = record.get("source_name", "Imported document")
                if not isinstance(raw, str) or len(raw) > 100000 or not isinstance(source, str) or len(source) > 200:
                    raise WorkflowError("Source name or source text is too long.")
                digest = hashlib.sha256(json.dumps({"raw": raw, "fields": fields}, sort_keys=True).encode()).hexdigest()
                existing = db.execute("SELECT id FROM documents WHERE source_hash=?", (digest,)).fetchone()
                if existing:
                    result.append({"id": existing["id"], "existing": True})
                    continue
                doc_id = uuid.uuid4().hex
                stamp = now()
                db.execute("INSERT INTO documents VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", (
                    doc_id, source, digest, raw, json.dumps(fields), record.get("document_type", "structured_record"),
                    json.dumps(record.get("warnings", [])), "draft", 1, stamp, stamp, None,
                ))
                self.audit(db, doc_id, "imported", actor, {"source_name": source, "fields": fields})
                result.append({"id": doc_id, "existing": False})
            self.invalidate_approvals(db)
        return result

    def import_text(self, text, source_name, actor):
        if not isinstance(text, str) or not text.strip() or len(text) > 100000:
            raise WorkflowError("Provide document text (maximum 100,000 characters).")
        parsed = parse_document(text.splitlines()).to_dict()
        # Explicit payee labels outrank organization headers for internal forms.
        if parsed["document_type"] == "check_request":
            for line in text.splitlines():
                match = re.match(r"\s*(?:Vendor Name|Pay To)\s*:?\s+(.+)", line, re.I)
                if match:
                    parsed["vendor"] = match.group(1).strip()
                    break
        return self.import_records([{"fields": {key: parsed.get(key) for key in FIELDS}, "raw_text": text,
            "source_name": source_name, "document_type": parsed["document_type"], "warnings": parsed["warnings"]}], actor)

    def import_csv(self, text, source_name, actor):
        if not isinstance(text, str) or len(text) > 1000000:
            raise WorkflowError("CSV must be text, maximum 1 MB.")
        reader = csv.DictReader(io.StringIO(text.lstrip('\ufeff')))
        headers = reader.fieldnames or []
        allowed = (FIELDS - MONEY_FIELDS) | {"subtotal", "tax", "total"}
        if len(headers) != len(set(headers)) or set(headers) - allowed or not {"vendor", "date", "total"} <= set(headers):
            raise WorkflowError("CSV needs vendor,date,total headers. Optional: document_number,subtotal,tax,account_code,department,notes. Unknown/duplicate headers are rejected.")
        records = []
        for index, row in enumerate(reader, 2):
            if None in row or any(v is None for v in row.values()):
                raise WorkflowError(f"CSV row {index} has the wrong number of columns.")
            if index > 501:
                raise WorkflowError("CSV import limit is 500 records.")
            fields = {key: row.get(key) or None for key in FIELDS - MONEY_FIELDS}
            for key in MONEY_FIELDS:
                fields[key] = money(row.get(key.removesuffix("_cents")))
            records.append({"fields": fields, "source_name": f"{source_name} · row {index}", "raw_text": json.dumps(row)})
        return self.import_records(records, actor)

    def edit(self, document_id, fields, revision, actor):
        fields = normalize_fields(fields)
        with self.connect(write=True) as db:
            row = self.get(db, document_id)
            self.check_revision(row, revision)
            if row["status"] not in ("draft", "approved"):
                raise WorkflowError("Only draft or approved records can be edited.", 409)
            before = json.loads(row["fields"])
            after = before | fields
            db.execute("UPDATE documents SET fields=?, status='draft', revision=revision+1, updated_at=? WHERE id=?", (json.dumps(after), now(), document_id))
            self.audit(db, document_id, "edited", actor, {"before": before, "after": after, "previous_status": row["status"]})
            self.invalidate_approvals(db)
        return self.detail(document_id)

    def check_revision(self, row, revision):
        if type(revision) is not int or row["revision"] != revision:
            raise WorkflowError("Record changed. Refresh before saving or reviewing.", 409)

    def transition(self, document_id, action, revision, actor, reason="", independent=False):
        with self.connect(write=True) as db:
            row = self.get(db, document_id)
            self.check_revision(row, revision)
            if action == "approve":
                if row["status"] != "draft":
                    raise WorkflowError("Only draft records can be approved.", 409)
                if independent and db.execute("SELECT 1 FROM events WHERE document_id=? AND action IN ('imported','edited') AND actor=? LIMIT 1", (document_id, actor)).fetchone():
                    raise WorkflowError("A different reviewer must approve a record you imported or corrected.", 409)
                issues = self.issues(db, row)
                if issues:
                    raise WorkflowError("Resolve validation issues before approval: " + " ".join(i["message"] for i in issues), 409)
                status = "approved"
            elif action == "reject":
                if row["status"] not in ("draft", "approved"):
                    raise WorkflowError("This record cannot be rejected.", 409)
                if not isinstance(reason, str) or not reason.strip() or len(reason) > 2000:
                    raise WorkflowError("Provide a rejection reason (maximum 2000 characters).")
                status = "rejected"
            elif action == "reopen":
                if row["status"] not in ("approved", "rejected"):
                    raise WorkflowError("Only approved or rejected records can be reopened.", 409)
                status = "draft"
            else:
                raise WorkflowError("Unknown review action.")
            db.execute("UPDATE documents SET status=?, revision=revision+1, updated_at=? WHERE id=?", (status, now(), document_id))
            self.audit(db, document_id, action, actor, {"reason": reason, "fields": json.loads(row["fields"])})
            self.invalidate_approvals(db)
        return self.detail(document_id)

    def update_rules(self, rules, revision, actor):
        rules = validate_rules(rules)
        with self.connect(write=True) as db:
            old = self.rules(db)
            if type(revision) is not int or old["revision"] != revision:
                raise WorkflowError("Rules changed. Reload before saving.", 409)
            if rules["currency"] != old["rules"]["currency"] and db.execute("SELECT 1 FROM documents LIMIT 1").fetchone():
                raise WorkflowError("Currency cannot change once records exist. Use a separate database for another currency.", 409)
            db.execute("UPDATE settings SET rules=?, revision=revision+1 WHERE id=1", (json.dumps(rules),))
            self.audit(db, None, "rules_updated", actor, {"before": old["rules"], "after": rules})
            # Require explicit approval under changed rules even when amounts still pass.
            for row in db.execute("SELECT id FROM documents WHERE status='approved'").fetchall():
                db.execute("UPDATE documents SET status='draft', revision=revision+1, updated_at=? WHERE id=?", (now(), row["id"]))
                self.audit(db, row["id"], "approval_invalidated", "system", {"reason": "Business rules changed"})
        return self.rules()

    def export(self, actor):
        with self.connect(write=True) as db:
            rows = db.execute("SELECT * FROM documents WHERE status='approved' ORDER BY created_at").fetchall()
            if not rows:
                raise WorkflowError("No approved records to export.", 409)
            for row in rows:
                if self.issues(db, row):
                    raise WorkflowError("An approved record no longer passes validation. Review it before exporting.", 409)
            export_id = uuid.uuid4().hex
            output = io.StringIO(newline="")
            writer = csv.writer(output)
            writer.writerow(["record_id", "vendor", "document_number", "date", "subtotal", "tax", "total", "currency", "account_code", "department", "notes"])
            rules = self.rules(db)["rules"]
            for row in rows:
                f = json.loads(row["fields"])
                amount = lambda key: "" if f.get(key) is None else f"{Decimal(f[key]) / 100:.2f}"
                writer.writerow([row["id"], csv_cell(f.get("vendor")), csv_cell(f.get("document_number")), f.get("date"), amount("subtotal_cents"), amount("tax_cents"), amount("total_cents"), rules["currency"], csv_cell(f.get("account_code")), csv_cell(f.get("department")), csv_cell(f.get("notes"))])
                db.execute("UPDATE documents SET status='exported', export_id=?, revision=revision+1, updated_at=? WHERE id=?", (export_id, now(), row["id"]))
                self.audit(db, row["id"], "exported", actor, {"export_id": export_id, "fields": f, "rules": rules})
            db.execute("INSERT INTO exports VALUES (?,?,?,?)", (export_id, output.getvalue(), now(), actor))
            self.audit(db, None, "export_created", actor, {"export_id": export_id, "record_count": len(rows)})
        return {"id": export_id, "record_count": len(rows), "download_url": f"/api/exports/{export_id}/download"}

    def exports(self):
        with self.connect() as db:
            return [dict(r) for r in db.execute("SELECT id,created_at,actor FROM exports ORDER BY created_at DESC")]

    def export_content(self, export_id):
        with self.connect() as db:
            row = db.execute("SELECT content FROM exports WHERE id=?", (export_id,)).fetchone()
            if not row:
                raise WorkflowError("Export not found.", 404)
            return row["content"]

    def events(self):
        with self.connect() as db:
            return [dict(r) | {"detail": json.loads(r["detail"])} for r in db.execute("SELECT * FROM events ORDER BY id DESC LIMIT 500")]
