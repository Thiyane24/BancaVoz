from fastapi.testclient import TestClient
import tomllib
from pathlib import Path

from bancavoz.api import app


def test_project_metadata_packages_web_and_runtime_dependencies():
    metadata = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    project = metadata["project"]
    assert project["dependencies"] == [
        "fastapi==0.150.0",
        "uvicorn==0.54.0",
        "pydantic==2.14.1",
        "mcp==1.30.0",
        "tzdata==2026.5",
        "psycopg[binary]==3.3.6",
        "boto3==1.42.63",
    ]
    assert project["optional-dependencies"]["dev"] == [
        "pytest==9.1.1",
        "httpx==0.28.1",
        "ruff==0.17.1",
        "pytest-cov==7.1.0",
        "mypy==2.4.0",
        "bandit==1.9.3",
        "pip-audit==2.10.0",
    ]
    assert "mcp" not in project["optional-dependencies"]
    assert metadata["tool"]["setuptools"]["package-data"]["bancavoz"] == [
        "web/*.html",
        "web/static/*",
    ]


def test_healthz():
    assert TestClient(app).get("/healthz").json() == {"status": "ok"}


def test_security_headers_and_readyz():
    response = TestClient(app).get("/healthz")
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["Content-Security-Policy"]
    assert TestClient(app).get("/readyz").status_code == 200


def test_static_pages_and_assets():
    client = TestClient(app)
    for path in ("/", "/app", "/sim"):
        response = client.get(path)
        assert response.status_code == 200
        assert "<!doctype html>" in response.text.lower()


def test_bearer_auth():
    client = TestClient(app)
    assert client.get("/summary").status_code == 401
    assert client.get("/summary", headers={"Authorization": "Bearer dev-token"}).status_code == 200


def test_http_generates_empty_idempotency_key():
    response = TestClient(app).post(
        "/expenses",
        headers={"Authorization": "Bearer dev-token"},
        json={"amount": "10", "idempotency_key": ""},
    )
    assert response.status_code == 200
    assert response.json()["idempotency_key"]


def test_simulator_utterance():
    response = TestClient(app).post("/sim/utterance", json={"utterance": "sold 2 rice at 10"})
    assert response.status_code == 200
    assert response.json()["tool_calls"][0]["tool"] == "log_sale"


def test_official_mcp_tools_list():
    headers = {"Authorization": "Bearer dev-token", "Accept": "application/json, text/event-stream"}
    with TestClient(app) as client:
        initialized = client.post(
            "/mcp/",
            headers=headers,
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-03-26",
                    "capabilities": {},
                    "clientInfo": {"name": "pytest", "version": "1"},
                },
            },
        )
        assert initialized.status_code == 200
        listed = client.post(
            "/mcp/",
            headers=headers,
            json={"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
        )
        assert listed.status_code == 200
        assert len(listed.json()["result"]["tools"]) == 10


def test_factory_isolates_database_and_mcp_paths_are_canonical():
    from bancavoz.api import create_app

    isolated = create_app({
        "database_url": "sqlite:///:memory:",
        "currency": "MZN",
        "bearer_token": "factory-token",
    })
    with TestClient(isolated) as client:
        assert client.get("/summary").status_code == 401
        assert client.get("/summary", headers={"Authorization": "Bearer factory-token"}).status_code == 200
        assert client.post("/mcp", headers={"Authorization": "Bearer factory-token"}).status_code != 307
        assert client.post("/mcp-legacy", headers={"Authorization": "Bearer factory-token"}).status_code == 404
        assert client.post("/simulator", data={"utterance": "hello"}).status_code == 405
