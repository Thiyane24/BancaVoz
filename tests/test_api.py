from fastapi.testclient import TestClient

from bancavoz.api import app


def test_healthz():
    assert TestClient(app).get("/healthz").json() == {"status": "ok"}


def test_bearer_auth():
    client = TestClient(app)
    assert client.get("/summary").status_code == 401
    assert client.get("/summary", headers={"Authorization": "Bearer dev-token"}).status_code == 200


def test_simulator_utterance():
    response = TestClient(app).post("/sim/utterance", json={"utterance": "sold 2 rice at 10"})
    assert response.status_code == 200
    assert response.json()["tool_calls"][0]["tool"] == "log_sale"
