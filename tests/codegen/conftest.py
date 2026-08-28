from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

import pytest


class MockApi:
    def __init__(self) -> None:
        self.routes = {}
        self.log = []
        self.url = ""


@pytest.fixture
def http_server():
    api = MockApi()

    class Handler(BaseHTTPRequestHandler):
        def _respond(self) -> None:
            parsed = urlparse(self.path)
            api.log.append((self.command, self.path, dict(self.headers)))
            route = api.routes.get(parsed.path)
            if route is None:
                self.send_response(404)
                self.end_headers()
                return
            query = {k: v[-1] for k, v in parse_qs(parsed.query).items()}
            body_len = int(self.headers.get("Content-Length") or 0)
            body = self.rfile.read(body_len) if body_len else b""
            status, payload, headers = route(query, dict(self.headers), body)
            data = json.dumps(payload).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            for key, value in headers.items():
                self.send_header(key, value)
            self.end_headers()
            self.wfile.write(data)

        do_GET = _respond
        do_POST = _respond

        def log_message(self, *args) -> None:  # silence
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    api.url = f"http://127.0.0.1:{server.server_port}"
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield api
    server.shutdown()
