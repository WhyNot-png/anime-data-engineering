"""Loopback-only HTTP interface for the local anime index."""

import json
import logging
import sqlite3
import threading
from dataclasses import asdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import cast
from urllib.parse import urlsplit

from research_graph.semantic_search import Encoder, read_index_info, search_index

ASSETS = Path(__file__).parent / "static"
MAX_BODY_BYTES = 65536
CSP = (
    "default-src 'self'; script-src 'self'; style-src 'self'; "
    "connect-src 'self'; img-src 'self'; base-uri 'none'; "
    "frame-ancestors 'none'; form-action 'self'"
)


class LocalAnimeServer(ThreadingHTTPServer):
    """Never binds to a public/network address; serializes model inference."""

    daemon_threads = True
    request_queue_size = 8

    def __init__(self, index: Path, encoder: Encoder, port: int = 8000) -> None:
        info = read_index_info(index)
        if (info.model_name, info.revision) != (encoder.model_name, encoder.revision):
            raise ValueError("Index model/revision does not match. Rebuild the search index.")
        self.index = index.resolve()
        self.encoder = encoder
        self.search_lock = threading.Lock()
        super().__init__(("127.0.0.1", port), AnimeHandler)


class AnimeHandler(BaseHTTPRequestHandler):
    """Small same-origin JSON API and whitelisted static assets, no uploads."""

    server_version = "LocalAnimeSearch"
    sys_version = ""

    @property
    def app(self) -> LocalAnimeServer:
        return cast(LocalAnimeServer, self.server)

    def log_message(self, format: str, *args: object) -> None:
        # Query text is sent in POST, not logged as part of the URL.
        logging.getLogger(__name__).debug(format, *args)

    def _send(self, status: int, content: bytes, content_type: str) -> None:
        try:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(content)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Security-Policy", CSP)
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("X-Frame-Options", "DENY")
            self.end_headers()
            self.wfile.write(content)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _json(self, status: int, payload: object) -> None:
        self._send(
            status,
            json.dumps(payload, ensure_ascii=False).encode(),
            "application/json; charset=utf-8",
        )

    def _allowed(self) -> bool:
        port = self.app.server_address[1]
        allowed = {f"127.0.0.1:{port}", f"localhost:{port}"}
        if port == 80:
            allowed.update({"127.0.0.1", "localhost"})
        host = (self.headers.get("Host") or "").casefold()
        origin = self.headers.get("Origin")
        if (
            host not in allowed
            or (origin is not None and origin not in {f"http://{name}" for name in allowed})
            or self.headers.get("Sec-Fetch-Site") == "cross-site"
        ):
            self._json(403, {"error": "Доступ разрешён только со страницы локального сайта."})
            return False
        return True

    def do_GET(self) -> None:
        if not self._allowed():
            return
        path = urlsplit(self.path).path
        if path == "/api/health":
            try:
                info = read_index_info(self.app.index)
            except (OSError, ValueError, sqlite3.Error):
                self._json(
                    503, {"error": "Индекс недоступен. Перестройте его и перезапустите сайт."}
                )
                return
            self._json(200, {"status": "ready", "index": asdict(info), "local_only": True})
            return
        routes = {
            "/": ("index.html", "text/html; charset=utf-8"),
            "/assets/style.css": ("style.css", "text/css; charset=utf-8"),
            "/assets/app.js": ("app.js", "text/javascript; charset=utf-8"),
        }
        if path not in routes:
            self._json(404, {"error": "Страница не найдена."})
            return
        filename, content_type = routes[path]
        self._send(200, (ASSETS / filename).read_bytes(), content_type)

    def do_POST(self) -> None:
        if not self._allowed():
            return
        if urlsplit(self.path).path != "/api/search":
            self._json(404, {"error": "Страница не найдена."})
            return
        if self.headers.get("Content-Type", "").split(";", 1)[0].strip() != "application/json":
            self._json(415, {"error": "Нужен запрос application/json."})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self._json(400, {"error": "Некорректная длина запроса."})
            return
        if not 0 < length <= MAX_BODY_BYTES or self.headers.get("Transfer-Encoding"):
            self._json(413, {"error": "Запрос слишком большой или пустой."})
            return
        self.connection.settimeout(10)
        try:
            payload = json.loads(self.rfile.read(length))
        except (json.JSONDecodeError, UnicodeDecodeError):
            self._json(400, {"error": "Некорректный JSON."})
            return
        except (TimeoutError, OSError):
            self._json(408, {"error": "Превышено время чтения запроса."})
            return
        if not isinstance(payload, dict):
            self._json(400, {"error": "Ожидается объект с query и top_k."})
            return
        query = payload.get("query")
        top_k = payload.get("top_k", 5)
        if not isinstance(query, str) or not 3 <= len(query.strip()) <= 4000:
            self._json(400, {"error": "Добавьте описание: от 3 до 4000 символов."})
            return
        if type(top_k) is not int or not 1 <= top_k <= 50:
            self._json(400, {"error": "Количество результатов должно быть от 1 до 50."})
            return
        if not self.app.search_lock.acquire(blocking=False):
            self._json(
                429,
                {"error": "Уже обрабатывается другой запрос. Попробуйте через несколько секунд."},
            )
            return
        try:
            hits = search_index(self.app.index, query, self.app.encoder, top_k=top_k)
            self._json(200, {"results": [asdict(hit) for hit in hits]})
        except (OSError, ValueError, RuntimeError, sqlite3.Error):
            self._json(
                503, {"error": "Не удалось выполнить поиск. Проверьте индекс и журнал сервера."}
            )
        finally:
            self.app.search_lock.release()
