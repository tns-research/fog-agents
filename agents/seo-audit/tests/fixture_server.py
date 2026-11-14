#!/usr/bin/env python3
"""
fixture_server.py

Serves the fictional swanbase.example test site of tests/fixtures/site/ on
127.0.0.1, with the exact statuses, redirects and headers listed in
routes.json (http.server alone would redirect /a to /a/ and could not serve
the defects the crawler must find). Standard library only.

    python3 tests/fixture_server.py --port 8765
    python3 scripts/crawl.py http://127.0.0.1:8765/ --as-origin https://swanbase.example --out-dir /tmp/run

Used by tests/run_tests.py in a background thread. Unknown paths answer 404.
"""

import argparse
import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Tuple

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.join(HERE, "fixtures", "site")


def make_handler(site_dir: str, routes_file: str = "routes.json"):
    with open(os.path.join(site_dir, routes_file), encoding="utf-8") as f:
        routes = json.load(f)["routes"]

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):  # quiet
            pass

        def do_GET(self):
            path = self.path.split("?", 1)[0].split("#", 1)[0]
            route = routes.get(path)
            if not route:
                body = b"<!doctype html><html><head><title>Not found</title></head><body><h1>Not found</h1></body></html>"
                self.send_response(404)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            body = b""
            if route.get("file"):
                with open(os.path.join(site_dir, "pages", route["file"]), "rb") as fh:
                    body = fh.read()
            headers = {"Content-Type": "text/html; charset=utf-8"}
            headers.update(route.get("headers", {}))
            self.send_response(route["status"])
            for k, v in headers.items():
                self.send_header(k, v)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    return Handler


def start(site_dir: str = SITE, port: int = 0, routes_file: str = "routes.json") -> Tuple[ThreadingHTTPServer, str]:
    server = ThreadingHTTPServer(("127.0.0.1", port), make_handler(site_dir, routes_file))
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    return server, f"http://127.0.0.1:{server.server_address[1]}"


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Serve the fictional test site.")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--site", default=SITE)
    ap.add_argument("--routes", default="routes.json", help="routes.json (as found) or routes-fixed.json (after the refresh)")
    a = ap.parse_args()
    srv, base = start(a.site, a.port, a.routes)
    print(f"serving {a.site} at {base}/ (Ctrl-C to stop)")
    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        srv.shutdown()
