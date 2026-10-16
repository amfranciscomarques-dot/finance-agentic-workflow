"""Loopback-only dashboard and JSON API over the existing workflow runner.

No frontend build or web framework is required. Request inputs are translated
to workflow parameters here; graph execution stays in the shared registry.
"""

from __future__ import annotations

import csv
import io
import json
import logging
import mimetypes
import threading
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from markdown_it import MarkdownIt

from . import workflows  # noqa: F401
from .llm import llm_available, resolve_model_provider
from .registry import registry, run_workflow
from .tools.base import company_name, known_sample_tickers

WEB_ROOT = Path(__file__).resolve().parent / "web"
MAX_REQUEST_BYTES = 1_048_576
logger = logging.getLogger(__name__)


def workflow_catalog() -> dict[str, Any]:
    model, provider = resolve_model_provider()
    return {
        "workflows": [
            {"name": wf.name, "title": wf.title, "description": wf.description}
            for wf in registry.all()
        ],
        "samples": [
            {"ticker": ticker, "company": company_name(ticker)} for ticker in known_sample_tickers()
        ],
        "model": model,
        "provider": provider,
        "llm_available": llm_available(),
    }


def request_params(payload: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """Accept browser inputs without exposing arbitrary local file paths."""
    name = payload.get("workflow")
    if not isinstance(name, str):
        raise ValueError("Choose a workflow.")
    registry.get(name)
    offline = payload.get("offline", True)
    if not isinstance(offline, bool):
        raise ValueError("offline must be a boolean.")
    params: dict[str, Any] = {"offline": offline}
    if name == "equity-research":
        params.update(ticker=payload.get("ticker"), news_limit=payload.get("news_limit", 5))
    elif name == "monitor":
        tickers = payload.get("tickers")
        if tickers is not None and not isinstance(tickers, (str, list)):
            raise ValueError("Watchlist must be a comma-separated string or list of tickers.")
        if isinstance(tickers, list) and len(tickers) > 50:
            raise ValueError("Use at most 50 watchlist tickers.")
        if isinstance(tickers, str) and len(tickers.split(",")) > 50:
            raise ValueError("Use at most 50 watchlist tickers.")
        params.update(tickers=tickers, news_limit=payload.get("news_limit", 3))
    elif name == "portfolio":
        positions = payload.get("positions")
        if positions is None:
            csv_text = payload.get("holdings_csv")
            if not isinstance(csv_text, str) or not csv_text.strip():
                raise ValueError("Provide a holdings CSV with ticker,shares columns.")
            reader = csv.DictReader(io.StringIO(csv_text.strip()), skipinitialspace=True)
            reader.fieldnames = [name.strip().lower() for name in (reader.fieldnames or [])]
            positions = list(reader)
        if not isinstance(positions, list) or not all(isinstance(row, dict) for row in positions):
            raise ValueError("Positions must be a list of holdings.")
        if len(positions) > 100:
            raise ValueError("Use at most 100 portfolio positions.")
        params["positions"] = positions
    elif name == "doc-analysis":
        text = payload.get("document_text", "")
        if not isinstance(text, str):
            raise ValueError("Document text must be a string.")
        params["ticker"] = payload.get("ticker") or None
        # The document provider accepts inline text when it contains a newline.
        # This also prevents a one-line document being interpreted as a file path.
        if text.strip():
            params["doc"] = text.strip() + "\n"
    else:
        raise ValueError("This workflow does not yet have a dashboard input form.")
    return name, params


def execute_request(payload: dict[str, Any]) -> dict[str, Any]:
    name, params = request_params(payload)
    result = run_workflow(name, **params)
    state = result.state
    data = {
        "equity-research": lambda: {
            "market": state.get("market", {}),
            "analysis": state.get("analysis", {}),
        },
        "portfolio": lambda: state.get("metrics", {}),
        "doc-analysis": lambda: state.get("analysis", {}),
        "monitor": lambda: state.get("scan", {}),
    }[name]()
    renderer = MarkdownIt("commonmark", {"html": False}).enable("table")
    return {
        "workflow": name,
        "markdown": result.markdown,
        "html": renderer.render(result.markdown),
        "metadata": result.metadata,
        "data": data,
    }


class DashboardServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, port: int = 8765) -> None:
        super().__init__(("127.0.0.1", port), DashboardHandler)
        self.run_slots = threading.BoundedSemaphore(2)


class DashboardHandler(BaseHTTPRequestHandler):
    server: DashboardServer

    def _local_request(self) -> bool:
        """Require our local Host and same-origin browser requests."""
        port = self.server.server_port
        host = self.headers.get("Host", "")
        allowed_hosts = {f"127.0.0.1:{port}", f"localhost:{port}"}
        allowed_origins = {f"http://{name}" for name in allowed_hosts}
        return host in allowed_hosts and (
            not self.headers.get("Origin") or self.headers["Origin"] in allowed_origins
        )

    def _send(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'",
        )
        self.end_headers()
        self.wfile.write(body)

    def _json(self, status: int, value: dict[str, Any]) -> None:
        self._send(
            status, json.dumps(value, allow_nan=False).encode(), "application/json; charset=utf-8"
        )

    def do_GET(self) -> None:
        if not self._local_request():
            self._json(HTTPStatus.FORBIDDEN, {"error": "Local dashboard requests only."})
            return
        path = urlsplit(self.path).path
        if path == "/healthz":
            self._json(HTTPStatus.OK, {"status": "ok", "app": "finance-workflow"})
        elif path == "/api/workflows":
            self._json(HTTPStatus.OK, workflow_catalog())
        elif path in {"/", "/app.js", "/styles.css", "/icon.svg"}:
            asset = WEB_ROOT / ("index.html" if path == "/" else path[1:])
            content_type = mimetypes.guess_type(asset.name)[0] or "application/octet-stream"
            self._send(HTTPStatus.OK, asset.read_bytes(), f"{content_type}; charset=utf-8")
        else:
            self._json(HTTPStatus.NOT_FOUND, {"error": "Not found."})

    def do_POST(self) -> None:
        if not self._local_request():
            self._json(HTTPStatus.FORBIDDEN, {"error": "Local dashboard requests only."})
            return
        if urlsplit(self.path).path != "/api/run":
            self._json(HTTPStatus.NOT_FOUND, {"error": "Not found."})
            return
        if self.headers.get("Content-Type", "").split(";", 1)[0] != "application/json":
            self._json(HTTPStatus.UNSUPPORTED_MEDIA_TYPE, {"error": "Send application/json."})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > MAX_REQUEST_BYTES:
                self._json(
                    HTTPStatus.REQUEST_ENTITY_TOO_LARGE, {"error": "Send a JSON body under 1 MB."}
                )
                return
            payload = json.loads(self.rfile.read(length))
            if not isinstance(payload, dict):
                raise ValueError("Request must be a JSON object.")
        except (ValueError, UnicodeError) as exc:
            self._json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
            return
        if not self.server.run_slots.acquire(blocking=False):
            self._json(
                HTTPStatus.SERVICE_UNAVAILABLE,
                {"error": "Two workflows are already running. Try again shortly."},
            )
            return
        try:
            result = execute_request(payload)
            self._json(HTTPStatus.OK, result)
        except (KeyError, ValueError, FileNotFoundError, TypeError) as exc:
            self._json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
        except Exception:
            logger.exception("Dashboard workflow failed")
            self._json(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                {"error": "Workflow failed. Check the server log for details."},
            )
        finally:
            self.server.run_slots.release()

    def log_message(self, format: str, *args: Any) -> None:
        logger.info(format, *args)


def serve(port: int = 8765, open_browser: bool = False) -> None:
    if not 1 <= port <= 65535:
        raise ValueError("Port must be between 1 and 65535.")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    with DashboardServer(port) as server:
        url = f"http://127.0.0.1:{server.server_port}"
        print(f"Finance Workflow dashboard: {url}", flush=True)
        if open_browser:
            webbrowser.open(url)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\nDashboard stopped.", flush=True)
