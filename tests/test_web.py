"""Loopback-only integration tests: local HTTP, fake embeddings, no Internet."""

import http.client
import json
import threading
from collections.abc import Iterator, Sequence
from pathlib import Path
from typing import Literal

import pytest
from typer.testing import CliRunner

from research_graph import search_cli, web
from research_graph.cli import app
from research_graph.semantic_search import Anime, build_index


class Encoder:
    model_name = "web-test"
    revision = "test-v1"

    def encode(
        self, texts: Sequence[str], *, kind: Literal["query", "passage"]
    ) -> list[list[float]]:
        return [[1.0, 0.0] for _ in texts]


@pytest.fixture
def server(tmp_path: Path) -> Iterator[web.LocalAnimeServer]:
    path = tmp_path / "index.db"
    build_index([Anime("1", "Example", "A story about space.", "Sci-Fi")], path, Encoder())
    instance = web.LocalAnimeServer(path, Encoder(), 0)
    thread = threading.Thread(
        target=instance.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True
    )
    thread.start()
    yield instance
    instance.shutdown()
    instance.server_close()
    thread.join(timeout=2)


def request(
    server: web.LocalAnimeServer,
    method: str,
    path: str,
    body: bytes | None = None,
    headers: dict[str, str] | None = None,
) -> tuple[int, dict[str, str], bytes]:
    connection = http.client.HTTPConnection("127.0.0.1", server.server_address[1], timeout=5)
    try:
        connection.request(method, path, body=body, headers=headers or {})
        response = connection.getresponse()
        return response.status, dict(response.getheaders()), response.read()
    finally:
        connection.close()


@pytest.mark.parametrize(
    "path,kind",
    [("/", "text/html"), ("/assets/app.js", "text/javascript"), ("/assets/style.css", "text/css")],
)
def test_assets_and_security_headers(server: web.LocalAnimeServer, path: str, kind: str) -> None:
    status, headers, body = request(server, "GET", path)
    assert status == 200 and body
    assert kind in headers["Content-Type"]
    assert "script-src 'self'" in headers["Content-Security-Policy"]
    assert "unsafe-inline" not in headers["Content-Security-Policy"]
    assert headers["X-Content-Type-Options"] == "nosniff"
    assert server.server_address[0] == "127.0.0.1"


def test_health_search_and_routing(server: web.LocalAnimeServer) -> None:
    status, _, body = request(server, "GET", "/api/health")
    assert status == 200
    assert json.loads(body)["index"]["count"] == 1
    status, _, body = request(
        server,
        "POST",
        "/api/search",
        json.dumps({"query": "космос", "top_k": 3}).encode(),
        {"Content-Type": "application/json"},
    )
    assert status == 200
    assert json.loads(body)["results"][0]["anime"]["title"] == "Example"
    for path in ["/api/search", "/../requirements-search.txt", "/assets/../../config.py"]:
        assert request(server, "GET", path)[0] == 404
    assert request(server, "POST", "/other")[0] == 404


@pytest.mark.parametrize(
    "headers",
    [
        {"Host": "evil.example"},
        {"Origin": "https://evil.example"},
        {"Origin": "null"},
        {"Sec-Fetch-Site": "cross-site"},
    ],
)
def test_blocks_foreign_hosts_and_origins(
    server: web.LocalAnimeServer, headers: dict[str, str]
) -> None:
    assert request(server, "GET", "/api/health", headers=headers)[0] == 403


def test_local_origin_is_allowed(server: web.LocalAnimeServer) -> None:
    origin = f"http://127.0.0.1:{server.server_address[1]}"
    assert request(server, "GET", "/api/health", headers={"Origin": origin})[0] == 200


@pytest.mark.parametrize(
    "payload",
    [
        [],
        {},
        {"query": 15},
        {"query": "  "},
        {"query": "x" * 4001},
        {"query": "abc", "top_k": True},
        {"query": "abc", "top_k": 0},
        {"query": "abc", "top_k": 51},
    ],
)
def test_invalid_payloads(server: web.LocalAnimeServer, payload: object) -> None:
    status, _, _ = request(
        server,
        "POST",
        "/api/search",
        json.dumps(payload).encode(),
        {"Content-Type": "application/json"},
    )
    assert status == 400


def test_bad_http_bodies(server: web.LocalAnimeServer) -> None:
    assert request(server, "POST", "/api/search", b"x", {"Content-Type": "text/plain"})[0] == 415
    assert (
        request(server, "POST", "/api/search", b"{", {"Content-Type": "application/json"})[0] == 400
    )
    assert (
        request(
            server,
            "POST",
            "/api/search",
            b"x",
            {"Content-Type": "application/json", "Content-Length": "invalid"},
        )[0]
        == 400
    )
    assert (
        request(
            server,
            "POST",
            "/api/search",
            b"x" * (web.MAX_BODY_BYTES + 1),
            {"Content-Type": "application/json"},
        )[0]
        == 413
    )


def test_busy_model_is_not_run_twice(server: web.LocalAnimeServer) -> None:
    server.search_lock.acquire()
    try:
        status, _, _ = request(
            server,
            "POST",
            "/api/search",
            b'{"query":"space"}',
            {"Content-Type": "application/json"},
        )
        assert status == 429
    finally:
        server.search_lock.release()


def test_deleted_index_returns_service_error(server: web.LocalAnimeServer) -> None:
    server.index.unlink()
    assert request(server, "GET", "/api/health")[0] == 503
    assert (
        request(
            server,
            "POST",
            "/api/search",
            b'{"query":"space"}',
            {"Content-Type": "application/json"},
        )[0]
        == 503
    )
    assert not server.search_lock.locked()


def test_mismatched_model_cannot_start(tmp_path: Path) -> None:
    path = tmp_path / "index.db"
    build_index([Anime("1", "Title", "A plot")], path, Encoder())
    encoder = Encoder()
    encoder.revision = "wrong"
    with pytest.raises(ValueError, match="model/revision"):
        web.LocalAnimeServer(path, encoder, 0)


def test_serve_cli(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "index.db"
    build_index([Anime("1", "Title", "Plot")], path, Encoder())
    closed: list[bool] = []

    class FakeServer:
        def __init__(self, *args: object) -> None:
            pass

        def serve_forever(self) -> None:
            raise KeyboardInterrupt

        def server_close(self) -> None:
            closed.append(True)

    monkeypatch.setattr(search_cli, "SentenceEncoder", Encoder)
    monkeypatch.setattr(web, "LocalAnimeServer", FakeServer)
    result = CliRunner().invoke(app, ["anime", "serve", "--index", str(path)])
    assert result.exit_code == 0, result.output
    assert "http://127.0.0.1:8000" in result.output
    assert closed == [True]
    result = CliRunner().invoke(app, ["anime", "serve", "--index", str(tmp_path / "missing.db")])
    assert result.exit_code == 2 and "Cannot start website" in result.output
