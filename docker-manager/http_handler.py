"""HTTP routes, request checks and responses for the catalog editor."""

import json
from http.server import SimpleHTTPRequestHandler
from urllib.parse import parse_qs, urlsplit

from catalog import ConflictError


ITEM_ROUTES = {"/api/parts": "parts", "/api/schemes": "schemes"}
STATIC_ROUTES = {"/", "/index.html", "/app.js", "/metadata.js", "/style.css"}


def make_handler(catalog, static_path):
    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(static_path), **kwargs)

        def end_headers(self):
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'self'; frame-ancestors 'none'; base-uri 'none'")
            super().end_headers()

        def reply(self, status, data):
            raw = json.dumps(data, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def call(self, operation, invalid_status=422, missing_status=500, error_prefix=""):
            """Map storage errors to the API's status codes in one place."""
            try:
                result = operation()
            except ConflictError as error:
                self.reply(409, {"error": str(error)})
            except FileNotFoundError as error:
                self.reply(missing_status, {"error": error_prefix + str(error)})
            except (ValueError, KeyError, UnicodeError) as error:
                self.reply(invalid_status, {"error": error_prefix + str(error)})
            except OSError as error:
                self.reply(500, {"error": error_prefix + str(error)})
            else:
                self.reply(200, result)

        def filename(self):
            query = parse_qs(urlsplit(self.path).query, keep_blank_values=True)
            return query["file"][0] if "file" in query else None

        def do_GET(self):
            route = urlsplit(self.path).path
            if route in ITEM_ROUTES:
                kind, filename = ITEM_ROUTES[route], self.filename()
                self.call(lambda: catalog.list_items(kind) if filename is None else catalog.load_item(kind, filename),
                          missing_status=404, error_prefix="Cannot read catalog: ")
            elif route == "/api/tags":
                self.call(catalog.load_tags, error_prefix="Could not read the file: ")
            elif route in ("/parts", "/schemes"):
                self.path = "/metadata.html"
                super().do_GET()
            elif route in STATIC_ROUTES:
                super().do_GET()
            else:
                self.reply(404, {"error": "Page not found."})

        def do_POST(self):
            route = urlsplit(self.path).path
            if route not in {"/api/tags", "/api/indexes", *ITEM_ROUTES}:
                self.reply(404, {"error": "Page not found."})
                return
            origin = self.headers.get("Origin")
            if origin and urlsplit(origin).netloc != self.headers.get("Host"):
                self.reply(403, {"error": "Requests from another site are not allowed."})
                return
            if self.headers.get_content_type() != "application/json":
                self.reply(415, {"error": "Expected application/json."})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= 1_000_000:
                    self.reply(413, {"error": "Invalid request size (maximum 1 MB)."})
                    return
                data = json.loads(self.rfile.read(length))
                if not isinstance(data, dict):
                    raise ValueError("Expected a JSON object.")
            except (ValueError, UnicodeError) as error:
                self.reply(400, {"error": str(error)})
                return
            if route in ITEM_ROUTES:
                kind, filename = ITEM_ROUTES[route], self.filename()
                self.call(lambda: catalog.save_item(kind, filename, data), invalid_status=400,
                          missing_status=404, error_prefix="Save failed: ")
            elif route == "/api/tags":
                self.call(lambda: catalog.save_tags(data), invalid_status=400, error_prefix="Save failed: ")
            elif data:
                self.reply(400, {"error": "Expected an empty JSON object."})
            else:
                self.call(catalog.rebuild_indexes, error_prefix="Cannot build indexes: ")

    return Handler
