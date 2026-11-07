#!/usr/bin/env python3
"""Run the dependency-free catalog metadata editor."""

import argparse
from http.server import ThreadingHTTPServer
from pathlib import Path

from catalog import Catalog
from http_handler import make_handler


def make_server(tags_path, host="0.0.0.0", port=8080):
    catalog = Catalog(tags_path)
    static_path = Path(__file__).resolve().parent / "static"
    return ThreadingHTTPServer((host, port), make_handler(catalog, static_path))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tags", type=Path, default=Path(__file__).resolve().parent.parent / "tags.json")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8080)
    args = parser.parse_args()
    server = make_server(args.tags, args.host, args.port)
    print(f"Catalog manager: http://{args.host}:{args.port} • {args.tags}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
