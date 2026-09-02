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
            if isinstance(payload, (str, bytes)):
                data = payload.encode() if isinstance(payload, str) else payload
                content_type = headers.get("Content-Type", "application/xml")
            else:
                data = json.dumps(payload).encode()
                content_type = "application/json"
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            for key, value in headers.items():
                if key.lower() == "content-type":
                    continue
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


@pytest.fixture(scope="session")
def spark_session():
    """A real, local[1] SparkSession for `@pytest.mark.spark` execution tests.

    `pyspark.pipelines` (the `dp.table` decorator) only ships on Databricks
    runtimes, not in the OSS `pyspark` wheel this repo depends on — so a
    fake `pyspark.pipelines` module (a `table(**kw)` that's just a no-op
    decorator) is installed into `sys.modules` before any generated script
    is exec'd, letting the *unmodified* `generate()` output run here,
    decorator included, exactly as shipped.
    """
    from pyspark.sql import SparkSession

    from tests.codegen.helpers import install_fake_pipelines

    install_fake_pipelines()

    session = (
        SparkSession.builder.master("local[1]")
        .appName("polymo-tests")
        .config("spark.ui.enabled", "false")
        .config("spark.sql.shuffle.partitions", "1")
        .getOrCreate()
    )
    yield session
    session.stop()
