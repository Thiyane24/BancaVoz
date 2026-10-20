from fastapi.testclient import TestClient

from bancavoz.api import app


def test_healthz():
    assert TestClient(app).get("/healthz").json() == {"status": "ok"}


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
