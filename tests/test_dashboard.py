"""Exercise the actual local API, including its browser request boundary."""

from __future__ import annotations

import http.client
import json
import threading

import pytest

from finance_workflow.dashboard import DashboardServer, request_params


@pytest.fixture(scope="module")
def server():
    instance = DashboardServer(port=0)
    thread = threading.Thread(target=instance.serve_forever, daemon=True)
    thread.start()
    yield instance
    instance.shutdown()
    instance.server_close()
    thread.join(timeout=3)


def request(server, path, payload=None, headers=None):
    connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=15)
    body = json.dumps(payload) if payload is not None else None
    request_headers = {"Content-Type": "application/json", **(headers or {})}
    try:
        connection.request("POST" if payload is not None else "GET", path, body, request_headers)
        response = connection.getresponse()
        return response.status, response.getheaders(), response.read()
    finally:
        connection.close()


def test_catalog_and_static_assets(server):
    status, _, body = request(server, "/api/workflows")
    catalog = json.loads(body)
    assert status == 200
    assert len(catalog["workflows"]) == 4
    assert {sample["ticker"] for sample in catalog["samples"]} == {"AAPL", "MSFT", "NVDA"}
    for path in ["/", "/app.js", "/styles.css", "/icon.svg", "/healthz"]:
        status, headers, body = request(server, path)
        assert status == 200
        assert body
        assert "frame-ancestors 'none'" in dict(headers)["Content-Security-Policy"]


@pytest.mark.parametrize(
    "payload",
    [
        {"workflow": "equity-research", "ticker": "AAPL"},
        {"workflow": "portfolio", "holdings_csv": "ticker,shares\nAAPL,120\nMSFT,60\nNVDA,200"},
        {"workflow": "doc-analysis", "ticker": "MSFT"},
        {"workflow": "monitor", "tickers": "AAPL,MSFT,NVDA"},
    ],
)
def test_all_four_workflows_run_through_http_in_sample_mode(server, payload):
    status, _, body = request(server, "/api/run", payload)
    result = json.loads(body)
    assert status == 200, result
    assert result["workflow"] == payload["workflow"]
    assert result["markdown"]
    assert "<h1>" in result["html"]
    assert result["metadata"]["used_llm"] is False
    assert set(result["metadata"]["sources"].values()) == {"sample"}


@pytest.mark.parametrize(
    "payload",
    [
        {"workflow": "unknown"},
        {"workflow": "equity-research", "ticker": "../AAPL"},
        {"workflow": "equity-research", "ticker": "AAPL", "offline": "false"},
        {"workflow": "monitor", "tickers": []},
        {"workflow": "portfolio", "positions": "examples/sample_portfolio.csv"},
        {"workflow": "portfolio", "holdings_csv": "ticker,shares\nAAPL,nan"},
    ],
)
def test_invalid_inputs_return_useful_errors(server, payload):
    status, _, body = request(server, "/api/run", payload)
    assert status == 400
    assert json.loads(body)["error"]


def test_browser_cannot_supply_local_file_paths():
    name, params = request_params(
        {"workflow": "doc-analysis", "file": "/etc/passwd", "document_text": "/etc/passwd"}
    )
    assert name == "doc-analysis"
    assert "file" not in params
    assert params["doc"] == "/etc/passwd\n"


@pytest.mark.parametrize("headers", [{"Origin": "https://example.com"}, {"Host": "example.com"}])
def test_foreign_browser_requests_rejected(server, headers):
    status, _, body = request(server, "/api/run", {"workflow": "monitor"}, headers)
    assert status == 403
    assert "Local" in json.loads(body)["error"]


def test_html_in_workflow_output_is_escaped(server, monkeypatch):
    from finance_workflow.workflow import WorkflowResult

    monkeypatch.setattr(
        "finance_workflow.dashboard.run_workflow",
        lambda *a, **k: WorkflowResult(
            workflow="monitor",
            params={},
            markdown='<script>alert("xss")</script>\n[bad](javascript:alert(1))',
        ),
    )
    status, _, body = request(server, "/api/run", {"workflow": "monitor"})
    html = json.loads(body)["html"]
    assert status == 200
    assert "<script>" not in html
    assert 'href="javascript:' not in html


def test_request_body_limit(server):
    # Oversized bodies are rejected from their headers before upload begins.
    status, _, body = request(server, "/api/run", {}, {"Content-Length": "1048577"})
    assert status == 413
    assert "under 1 MB" in json.loads(body)["error"]


def test_concurrent_run_limit(server):
    server.run_slots.acquire()
    server.run_slots.acquire()
    try:
        status, _, body = request(server, "/api/run", {"workflow": "monitor"})
        assert status == 503
        assert "already running" in json.loads(body)["error"]
    finally:
        server.run_slots.release()
        server.run_slots.release()
