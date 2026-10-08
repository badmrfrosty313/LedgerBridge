from __future__ import annotations

import argparse
import json
import logging
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from .core import Store, WorkflowError

ROOT = Path(__file__).parent
STATIC = ROOT / "static"
LOG = logging.getLogger("ledgerbridge")


def handler_for(store):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            LOG.info(fmt, *args)

        def respond(self, value, status=200, content_type="application/json; charset=utf-8", attachment=None):
            data = json.dumps(value, ensure_ascii=False).encode() if content_type.startswith("application/json") else value.encode() if isinstance(value, str) else value
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
            self.send_header("Referrer-Policy", "no-referrer")
            if attachment:
                self.send_header("Content-Disposition", f'attachment; filename="{attachment}"')
            self.end_headers()
            self.wfile.write(data)

        def guard(self):
            # Local single-user service: reject DNS rebinding and cross-site browser writes.
            host = self.headers.get("Host", "")
            expected = {f"localhost:{self.server.server_port}", f"127.0.0.1:{self.server.server_port}"}
            if host not in expected:
                raise WorkflowError("Unsupported host. Open the app using localhost or 127.0.0.1.", 403)
            origin = self.headers.get("Origin")
            if origin and origin not in {"http://" + h for h in expected}:
                raise WorkflowError("Cross-origin requests are not permitted.", 403)
            if self.headers.get("Sec-Fetch-Site") == "cross-site":
                raise WorkflowError("Cross-site requests are not permitted.", 403)

        def body(self):
            if self.headers.get("Content-Type", "").split(";")[0] != "application/json":
                raise WorkflowError("Use application/json.", 415)
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                raise WorkflowError("Invalid content length.") from None
            if not 0 < length <= 2 * 1024 * 1024:
                raise WorkflowError("Request must be between 1 byte and 2 MB.", 413)
            try:
                value = json.loads(self.rfile.read(length))
            except (ValueError, UnicodeError):
                raise WorkflowError("Invalid JSON.") from None
            if not isinstance(value, dict):
                raise WorkflowError("Request body must be an object.")
            return value

        def dispatch(self):
            self.guard()
            path = urlsplit(self.path).path
            if self.command == "GET":
                static_files = {"/": ("index.html", "text/html; charset=utf-8"), "/app.js": ("app.js", "text/javascript; charset=utf-8"), "/style.css": ("style.css", "text/css; charset=utf-8")}
                if path in static_files:
                    name, mime = static_files[path]
                    return self.respond((STATIC / name).read_bytes(), content_type=mime)
                if path == "/api/health":
                    return self.respond({"status": "ok", "version": "0.1.0", "mode": "local-single-user"})
                if path == "/api/documents":
                    return self.respond({"documents": store.list_documents()})
                if path == "/api/rules":
                    return self.respond(store.rules())
                if path == "/api/events":
                    return self.respond({"events": store.events()})
                if path == "/api/exports":
                    return self.respond({"exports": store.exports()})
                match = re.fullmatch(r"/api/documents/([a-f0-9]{32})", path)
                if match:
                    return self.respond(store.detail(match[1]))
                match = re.fullmatch(r"/api/exports/([a-f0-9]{32})/download", path)
                if match:
                    return self.respond(store.export_content(match[1]), content_type="text/csv; charset=utf-8", attachment=f"ledgerbridge-{match[1][:8]}.csv")
            if self.command == "POST":
                body = self.body()
                actor = body.get("actor", "")
                if path == "/api/import/text":
                    return self.respond({"records": store.import_text(body.get("text"), body.get("source_name", "Pasted document"), actor)}, 201)
                if path == "/api/import/csv":
                    return self.respond({"records": store.import_csv(body.get("text"), body.get("source_name", "Imported CSV"), actor)}, 201)
                if path == "/api/demo":
                    fixtures = json.loads((ROOT / "demo.json").read_text())["fixtures"]
                    result = []
                    for fixture in fixtures:
                        result.extend(store.import_text("\n".join(fixture["lines"]), "Demo · " + fixture["id"], actor))
                    return self.respond({"records": result}, 201)
                if path == "/api/exports":
                    return self.respond(store.export(actor), 201)
                match = re.fullmatch(r"/api/documents/([a-f0-9]{32})/(approve|reject|reopen)", path)
                if match:
                    return self.respond(store.transition(match[1], match[2], body.get("revision"), actor, body.get("reason", "")))
            if self.command == "PATCH":
                body = self.body()
                match = re.fullmatch(r"/api/documents/([a-f0-9]{32})", path)
                if match:
                    return self.respond(store.edit(match[1], body.get("fields"), body.get("revision"), body.get("actor", "")))
                if path == "/api/rules":
                    return self.respond(store.update_rules(body.get("rules"), body.get("revision"), body.get("actor", "")))
            raise WorkflowError("Route not found.", 404)

        def handle_request(self):
            try:
                self.dispatch()
            except WorkflowError as exc:
                self.respond({"error": str(exc)}, exc.status)
            except (BrokenPipeError, ConnectionResetError):
                pass
            except Exception:
                LOG.exception("Request failed")
                self.respond({"error": "Unexpected server error. See local server logs."}, 500)

        do_GET = handle_request
        do_POST = handle_request
        do_PATCH = handle_request

    return Handler


def main():
    parser = argparse.ArgumentParser(description="Run LedgerBridge locally")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--db", default="data/ledgerbridge.sqlite3")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    server = ThreadingHTTPServer(("127.0.0.1", args.port), handler_for(Store(args.db)))
    server.daemon_threads = True
    print(f"LedgerBridge is running at http://127.0.0.1:{server.server_port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
