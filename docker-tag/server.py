#!/usr/bin/env python3
"""Small, dependency-free editor for the catalog's JSON array of tags."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import tempfile
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit


def normalize_tags(value):
    if not isinstance(value, list) or any(not isinstance(tag, str) for tag in value):
        raise ValueError("tags.json must contain an array of strings.")
    tags = []
    seen = set()
    for tag in value:
        tag = tag.strip().lower()
        if not tag:
            raise ValueError("A tag cannot be empty.")
        if tag not in seen:
            tags.append(tag)
            seen.add(tag)
    return tags


def revision(raw):
    return hashlib.sha256(raw).hexdigest()


def atomic_write(path, raw):
    """Replace inside the mounted directory, without leaving partial JSON."""
    fd, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(name, path.stat().st_mode & 0o777 if path.exists() else 0o644)
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def make_server(tags_path, host="0.0.0.0", port=8080):
    tags_path = Path(tags_path).resolve()
    static_path = Path(__file__).resolve().parent / "static"
    lock = threading.Lock()

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

        def do_GET(self):
            route = urlsplit(self.path).path
            if route == "/api/tags":
                try:
                    with lock:
                        raw = tags_path.read_bytes()
                        original = json.loads(raw)
                        tags = normalize_tags(original)
                    self.reply(200, {"tags": tags, "revision": revision(raw), "normalized": tags != original})
                except (ValueError, UnicodeError) as error:
                    self.reply(422, {"error": str(error)})
                except OSError as error:
                    self.reply(500, {"error": f"Could not read the file: {error}"})
            elif route in ("/", "/index.html", "/app.js", "/style.css"):
                super().do_GET()
            else:
                self.reply(404, {"error": "Page not found."})

        def do_POST(self):
            if urlsplit(self.path).path != "/api/tags":
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
                if not isinstance(data, dict) or "tags" not in data or "revision" not in data:
                    raise ValueError("Missing tags or file revision.")
                tags = normalize_tags(data["tags"])
                if len(tags) != len(data["tags"]):
                    raise ValueError("Tags contain duplicates after normalization.")
                with lock:
                    old_raw = tags_path.read_bytes()
                    normalize_tags(json.loads(old_raw))
                    if data["revision"] != revision(old_raw):
                        self.reply(409, {"error": "The file has changed since it was loaded. Reload the page before making further edits."})
                        return
                    raw = (json.dumps(tags, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
                    atomic_write(tags_path.with_name(tags_path.name + ".bak"), old_raw)
                    atomic_write(tags_path, raw)
                self.reply(200, {"tags": tags, "revision": revision(raw), "normalized": False})
            except (ValueError, UnicodeError) as error:
                self.reply(400, {"error": str(error)})
            except OSError as error:
                self.reply(500, {"error": f"Save failed: {error}"})

    return ThreadingHTTPServer((host, port), Handler)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tags", type=Path, default=Path(__file__).resolve().parent.parent / "tags.json")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8080)
    args = parser.parse_args()
    server = make_server(args.tags, args.host, args.port)
    print(f"Tag manager: http://{args.host}:{args.port} • {args.tags}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
