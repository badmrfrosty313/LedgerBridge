"""WSGI adapter for the reviewed HTTP routing layer, served by Waitress."""

from io import BytesIO
from email.message import Message
from types import SimpleNamespace

from .server import handler_for


def application_for(store, auth, origin, port=8765):
    handler_class = handler_for(store, None, auth, origin, False)

    def app(environ, start_response):
        handler = handler_class.__new__(handler_class)
        handler.server = SimpleNamespace(server_port=port)
        handler.command = environ.get("REQUEST_METHOD", "GET")
        handler.path = environ.get("PATH_INFO", "/") + ("?" + environ["QUERY_STRING"] if environ.get("QUERY_STRING") else "")
        handler.headers = Message()
        for key, value in environ.items():
            # WSGI provides these as dedicated values. Never allow an HTTP_
            # alias to disagree with the bytes we actually read below.
            if key.startswith("HTTP_") and key not in ("HTTP_CONTENT_TYPE", "HTTP_CONTENT_LENGTH"):
                handler.headers[key[5:].replace("_", "-")] = value
        handler.headers["Content-Type"] = environ.get("CONTENT_TYPE", "")
        handler.headers["Content-Length"] = environ.get("CONTENT_LENGTH", "")
        handler._headers = []
        handler._status = 500
        handler.wfile = BytesIO()
        try:
            length = int(environ.get("CONTENT_LENGTH") or 0)
        except ValueError:
            length = -1
        if length < 0 or length > 2 * 1024 * 1024:
            from .core import WorkflowError
            handler.rfile = BytesIO()
            handler.respond({"error": "Invalid or excessive request size."}, 413)
        else:
            handler.rfile = BytesIO(environ["wsgi.input"].read(length) if length else b"")
            handler.handle_request()
        start_response(f"{handler._status} {handler.responses.get(handler._status, ('Unknown', ''))[0]}", handler._headers)
        return [handler.wfile.getvalue()]

    def send_response(self, code, message=None):
        self._status = code

    def send_header(self, keyword, value):
        self._headers.append((keyword, value))

    def end_headers(self):
        pass

    handler_class.send_response = send_response
    handler_class.send_header = send_header
    handler_class.end_headers = end_headers
    return app
