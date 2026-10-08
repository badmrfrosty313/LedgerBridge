from __future__ import annotations

import argparse
import json
import logging
import re
import threading
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from .core import Store, WorkflowError
from . import __version__

ROOT = Path(__file__).parent
STATIC = ROOT / "static"
LOG = logging.getLogger("ledgerbridge")


LOGIN_SLOTS = threading.BoundedSemaphore(4)


def handler_for(store, bridge=None, auth=None, public_origin=None, demo_mode=True):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            LOG.info(fmt, *args)

        def respond(self, value, status=200, content_type="application/json; charset=utf-8", attachment=None, headers=None):
            data = json.dumps(value, ensure_ascii=False).encode() if content_type.startswith("application/json") else value.encode() if isinstance(value, str) else value
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
            self.send_header("Referrer-Policy", "no-referrer")
            if public_origin and public_origin.startswith("https://"):
                self.send_header("Strict-Transport-Security", "max-age=31536000")
            if attachment:
                self.send_header("Content-Disposition", f'attachment; filename="{attachment}"')
            for name, value in (headers or {}).items():
                self.send_header(name, value)
            self.end_headers()
            self.wfile.write(data)

        def guard(self):
            # Only accept the configured public host. Reverse proxies must preserve Host.
            host = self.headers.get("Host", "")
            expected = {urlsplit(public_origin).netloc} if public_origin else {f"localhost:{self.server.server_port}", f"127.0.0.1:{self.server.server_port}"}
            if host not in expected:
                raise WorkflowError("Unsupported host.", 403)
            origin = self.headers.get("Origin")
            allowed_origins = {public_origin} if public_origin else {"http://" + h for h in expected}
            if origin and origin not in allowed_origins:
                raise WorkflowError("Cross-origin requests are not permitted.", 403)
            if self.headers.get("Sec-Fetch-Site") == "cross-site":
                raise WorkflowError("Cross-site requests are not permitted.", 403)

        def session_token(self):
            try:
                cookies = SimpleCookie()
                cookies.load(self.headers.get("Cookie", ""))
                name = "__Host-LedgerBridge" if public_origin and public_origin.startswith("https://") else "LedgerBridgeLocal"
                return (cookies[name].value if name in cookies else None), name
            except Exception:
                return None, "LedgerBridgeLocal"

        def require_role(self, role):
            if auth and self.identity.role not in ("admin", role):
                raise WorkflowError("Your account cannot perform this action.", 403)

        def login(self):
            if not LOGIN_SLOTS.acquire(blocking=False):
                raise WorkflowError("Too many login attempts. Try again shortly.", 429)
            try:
                body = self.body()
                token = auth.login(body.get("username", ""), body.get("password", ""))
            finally:
                LOGIN_SLOTS.release()
            name = "__Host-LedgerBridge" if public_origin and public_origin.startswith("https://") else "LedgerBridgeLocal"
            attributes = "; Secure" if name.startswith("__Host-") else ""
            return self.respond({"ok": True}, headers={"Set-Cookie": f"{name}={token}; Path=/; HttpOnly; SameSite=Strict; Max-Age=28800{attributes}"})

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
            self.identity = None
            token = None
            if auth:
                if self.command == "GET" and path in ("/login", "/login.js", "/style.css"):
                    names = {"/login": ("login.html", "text/html; charset=utf-8"), "/login.js": ("login.js", "text/javascript; charset=utf-8"), "/style.css": ("style.css", "text/css; charset=utf-8")}
                    name, mime = names[path]
                    return self.respond((STATIC / name).read_bytes(), content_type=mime)
                if self.command == "POST" and path == "/api/login":
                    return self.login()
                if self.command == "GET" and path == "/api/health":
                    return self.respond({"status": "ok", "version": __version__})
                token, cookie_name = self.session_token()
                self.identity = auth.identity(token)
                if not self.identity:
                    if path == "/":
                        return self.respond("", 303, "text/plain; charset=utf-8", headers={"Location": "/login"})
                    raise WorkflowError("Sign in to continue.", 401)
                if self.command in ("POST", "PATCH"):
                    supplied = self.headers.get("X-CSRF-Token", "")
                    import hmac
                    if not hmac.compare_digest(supplied, self.identity.csrf):
                        raise WorkflowError("Missing or invalid request token.", 403)
                if path == "/api/session" and self.command == "GET":
                    return self.respond({"username": self.identity.username, "role": self.identity.role, "csrf": self.identity.csrf, "demo_mode": demo_mode})
                if path == "/api/logout" and self.command == "POST":
                    auth.logout(token)
                    return self.respond({"ok": True}, headers={"Set-Cookie": f"{cookie_name}=; Path=/; HttpOnly; SameSite=Strict; Max-Age=0" + ("; Secure" if cookie_name.startswith("__Host-") else "")})
            if self.command == "GET":
                static_files = {"/": ("index.html", "text/html; charset=utf-8"), "/app.js": ("app.js", "text/javascript; charset=utf-8"), "/style.css": ("style.css", "text/css; charset=utf-8")}
                if path in static_files:
                    name, mime = static_files[path]
                    return self.respond((STATIC / name).read_bytes(), content_type=mime)
                if path == "/api/health":
                    return self.respond({"status": "ok", "version": __version__, "mode": "explicit-local-demo"})
                if path == "/api/documents":
                    return self.respond({"documents": store.list_documents()})
                if path == "/api/rules":
                    return self.respond(store.rules())
                if path == "/api/events":
                    return self.respond({"events": store.events()})
                if path == "/api/exports":
                    return self.respond({"exports": store.exports()})
                if path == "/api/bridge/status" and bridge:
                    return self.respond(bridge.status())
                if path == "/api/bridge/deliveries" and bridge:
                    return self.respond({"deliveries": bridge.deliveries()})
                match = re.fullmatch(r"/api/documents/([a-f0-9]{32})", path)
                if match:
                    return self.respond(store.detail(match[1]))
                match = re.fullmatch(r"/api/exports/([a-f0-9]{32})/download", path)
                if match:
                    return self.respond(store.export_content(match[1]), content_type="text/csv; charset=utf-8", attachment=f"ledgerbridge-{match[1][:8]}.csv")
            if self.command == "POST":
                body = self.body()
                actor = self.identity.username if auth else body.get("actor", "")
                if path == "/api/import/text":
                    self.require_role("reviewer")
                    return self.respond({"records": store.import_text(body.get("text"), body.get("source_name", "Pasted document"), actor)}, 201)
                if path == "/api/import/csv":
                    self.require_role("reviewer")
                    return self.respond({"records": store.import_csv(body.get("text"), body.get("source_name", "Imported CSV"), actor)}, 201)
                if path == "/api/demo" and demo_mode:
                    self.require_role("reviewer")
                    fixtures = json.loads((ROOT / "demo.json").read_text())["fixtures"]
                    result = []
                    for fixture in fixtures:
                        result.extend(store.import_text("\n".join(fixture["lines"]), "Demo · " + fixture["id"], actor))
                    return self.respond({"records": result}, 201)
                if path == "/api/exports":
                    self.require_role("admin")
                    return self.respond(store.export(actor), 201)
                match = re.fullmatch(r"/api/exports/([a-f0-9]{32})/send-demo", path)
                if match and bridge:
                    self.require_role("admin")
                    return self.respond(bridge.send(match[1], actor))
                match = re.fullmatch(r"/api/documents/([a-f0-9]{32})/(approve|reject|reopen)", path)
                if match:
                    self.require_role("reviewer")
                    return self.respond(store.transition(match[1], match[2], body.get("revision"), actor, body.get("reason", ""), independent=bool(auth)))
            if self.command == "PATCH":
                body = self.body()
                match = re.fullmatch(r"/api/documents/([a-f0-9]{32})", path)
                if match:
                    self.require_role("reviewer")
                    return self.respond(store.edit(match[1], body.get("fields"), body.get("revision"), self.identity.username if auth else body.get("actor", "")))
                if path == "/api/rules":
                    self.require_role("admin")
                    return self.respond(store.update_rules(body.get("rules"), body.get("revision"), self.identity.username if auth else body.get("actor", "")))
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
    parser = argparse.ArgumentParser(description="Run LedgerBridge behind an HTTPS proxy, or explicitly in local mode")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--db", default="data/ledgerbridge.sqlite3")
    parser.add_argument("--demo-erp-port", type=int, default=8766)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--public-origin", help="HTTPS origin, for example https://ledger.example.com")
    mode.add_argument("--local-auth", action="store_true", help="Authenticated loopback test mode")
    mode.add_argument("--local-demo", action="store_true", help="Unauthenticated demo on loopback only")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    from .bridge import DemoBridge
    from .auth import Auth
    if args.public_origin:
        parsed = urlsplit(args.public_origin)
        if parsed.scheme != "https" or not parsed.hostname or parsed.path or parsed.query or parsed.fragment or parsed.username or parsed.password or args.public_origin.endswith("/"):
            parser.error("--public-origin must be an HTTPS origin without a path, query, credentials, or trailing slash")
    if args.local_demo:
        if args.db != "data/ledgerbridge.sqlite3":
            parser.error("Local demo uses a separate fixed database; --db is unavailable in --local-demo mode")
        args.db = "data/ledgerbridge-demo.sqlite3"
    elif args.local_auth and args.db == "data/ledgerbridge.sqlite3":
        args.db = "data/ledgerbridge-local.sqlite3"
    store = Store(args.db)
    auth = None if args.local_demo else Auth(store)
    if auth and not auth.has_users():
        parser.error("No users exist. Run: python -m ledgerbridge.admin add-user admin --role admin")
    bridge = DemoBridge(store, args.demo_erp_port) if not args.public_origin else None
    origin = args.public_origin or (f"http://127.0.0.1:{args.port}" if args.local_auth else None)
    if args.public_origin:
        try:
            from waitress import serve
        except ImportError:
            parser.error("Production mode needs Waitress. Run: python -m pip install -r requirements-prod.txt")
        from .wsgi import application_for
        print(f"Serving {origin} through a trusted HTTPS reverse proxy on 127.0.0.1:{args.port}", flush=True)
        serve(application_for(store, auth, origin, args.port), host="127.0.0.1", port=args.port,
              threads=8, max_request_body_size=2 * 1024 * 1024, max_request_header_size=16384,
              connection_limit=100, channel_timeout=30, ident="LedgerBridge")
        return
    server = ThreadingHTTPServer(("127.0.0.1", args.port), handler_for(store, bridge, auth, origin, bool(args.local_demo or args.local_auth)))
    server.daemon_threads = True
    print(f"LedgerBridge is running at {origin or 'http://127.0.0.1:' + str(server.server_port)}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
