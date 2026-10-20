import asyncio
import tomllib
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from bancavoz.api import create_app


@pytest.fixture
def isolated_app(tmp_path):
    return create_app({
        "database_url": f"sqlite:///{tmp_path / 'test.db'}",
        "currency": "MZN",
        "bearer_token": "dev-token",
    })


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


def test_healthz(isolated_app):
    assert TestClient(isolated_app).get("/healthz").json() == {"status": "ok"}


def test_security_headers_and_readyz(isolated_app):
    response = TestClient(isolated_app).get("/healthz")
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["Content-Security-Policy"]
    assert TestClient(isolated_app).get("/readyz").status_code == 200


def test_authenticated_requests_emit_request_id_and_rate_limit_headers(isolated_app):
    client = TestClient(isolated_app)
    response = client.get("/summary", headers={"Authorization": f"Bearer {isolated_app.state.bearer_token}"})
    assert response.status_code == 200
    assert response.headers["X-Request-ID"]
    assert response.headers["X-RateLimit-Limit"]
    assert response.headers["X-RateLimit-Remaining"]


def test_static_pages_and_assets(isolated_app):
    client = TestClient(isolated_app)
    for path in ("/", "/app", "/sim"):
        response = client.get(path)
        assert response.status_code == 200
        assert "<!doctype html>" in response.text.lower()


def test_bearer_auth(isolated_app):
    client = TestClient(isolated_app)
    assert client.get("/summary").status_code == 401
    assert client.get("/summary", headers={"Authorization": "Bearer dev-token"}).status_code == 200


def test_http_generates_empty_idempotency_key(isolated_app):
    response = TestClient(isolated_app).post(
        "/expenses",
        headers={"Authorization": "Bearer dev-token"},
        json={"amount": "10", "idempotency_key": ""},
    )
    assert response.status_code == 200
    assert response.json()["idempotency_key"]


def test_simulator_utterance(isolated_app):
    response = TestClient(isolated_app).post("/sim/utterance", json={"utterance": "sold 2 rice at 10"})
    assert response.status_code == 200
    assert response.json()["tool_calls"][0]["tool"] == "log_sale"


def test_official_mcp_tools_list(isolated_app):
    headers = {"Authorization": "Bearer dev-token", "Accept": "application/json, text/event-stream"}
    with TestClient(isolated_app) as client:
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


def test_entries_credits_and_command_are_authenticated_and_console_wired():
    from bancavoz.api import create_app

    isolated = create_app({
        "database_url": "sqlite:///:memory:",
        "currency": "MZN",
        "bearer_token": "factory-token",
    })
    with TestClient(isolated) as client:
        assert client.get("/entries").status_code == 401
        assert client.get("/credits").status_code == 401
        assert client.post("/command", json={"utterance": "how did today go"}).status_code == 401
        headers = {"Authorization": "Bearer factory-token"}
        assert client.get("/entries", headers=headers).status_code == 200
        assert client.get("/credits", headers=headers).status_code == 200
        assert client.post("/command", headers=headers,
                           json={"utterance": "how did today go"}).status_code == 200
    app_js = Path("bancavoz/web/static/app.js").read_text(encoding="utf-8")
    app_html = Path("bancavoz/web/app.html").read_text(encoding="utf-8")
    assert 'api("/entries")' in app_js
    assert 'api("/credits")' in app_js
    assert 'api("/command"' in app_js
    assert "Recent entries" in app_html


def test_http_idempotency_conflict_is_409_for_all_write_routes():
    from bancavoz.api import create_app

    isolated = create_app({
        "database_url": "sqlite:///:memory:",
        "currency": "MZN",
        "bearer_token": "factory-token",
    })
    headers = {"Authorization": "Bearer factory-token"}
    with TestClient(isolated) as client:
        writes = [
            ("/sales", {"unit_price": "10", "product": "rice", "idempotency_key": "same"}),
            ("/expenses", {"amount": "2", "product": "transport", "idempotency_key": "same-expense"}),
            ("/credits", {"amount": "5", "party": "Maria", "idempotency_key": "same-credit"}),
            ("/payments", {"amount": "1", "party": "Maria", "idempotency_key": "same-payment"}),
        ]
        for path, payload in writes:
            assert client.post(path, headers=headers, json=payload).status_code == 200
            changed = dict(payload)
            if path == "/sales":
                changed["unit_price"] = "99"
            elif path == "/payments":
                changed["amount"] = "2"
            else:
                changed["amount"] = "99"
            assert client.post(path, headers=headers, json=changed).status_code == 409


def test_six_demo_utterances_are_handled_without_server_errors():
    from bancavoz.api import create_app

    isolated = create_app({"database_url": "sqlite:///:memory:", "bearer_token": "factory-token"})
    with TestClient(isolated) as client:
        utterances = [
            "sold 2 rice at 10",
            "Maria owes half",
            "Maria paid 10",
            "undo that",
            "spent 200 on transport",
            "how did today go",
            "end of day digest",
        ]
        for utterance in utterances:
            response = client.post("/sim/utterance", json={"utterance": utterance})
            assert response.status_code == 200
            assert response.json()["speech"]
        assert client.post("/sim/utterance", json={"utterance": "Maria owes half"}).json()["tool_calls"][0]["tool"] == "log_sale"
        assert client.post("/sim/utterance", json={"utterance": "spent 200 on transport"}).json()["data"]["product"] == "transport"
        assert client.post("/sim/utterance", json={"utterance": "end of day digest"}).json()["tool_calls"][0]["tool"] == "get_daily_digest"


def test_real_mcp_client_can_call_tools_on_both_mcp_paths():
    from mcp import ClientSession
    from mcp.client.streamable_http import streamable_http_client

    from bancavoz.api import create_app

    isolated = create_app({"database_url": "sqlite:///:memory:", "bearer_token": "factory-token"})

    async def exercise(path: str):
        async with isolated.router.lifespan_context(isolated):
            transport = httpx.ASGITransport(app=isolated)
            async with (
                httpx.AsyncClient(transport=transport, base_url="http://testserver",
                                  headers={"Authorization": "Bearer factory-token"}) as client,
                streamable_http_client(f"http://testserver{path}", http_client=client) as streams,
                ClientSession(*streams[:2]) as session,
            ):
                        await session.initialize()
                        result = await session.call_tool("check_low_stock", {})
                        assert result is not None

    async def both():
        async with isolated.router.lifespan_context(isolated):
            await exercise_with_lifespan("/mcp")
            await exercise_with_lifespan("/mcp/")

    async def exercise_with_lifespan(path: str):
        transport = httpx.ASGITransport(app=isolated)
        async with (
            httpx.AsyncClient(transport=transport, base_url="http://testserver",
                              headers={"Authorization": "Bearer factory-token"}) as client,
            streamable_http_client(f"http://testserver{path}", http_client=client) as streams,
            ClientSession(*streams[:2]) as session,
        ):
                    await session.initialize()
                    result = await session.call_tool("check_low_stock", {})
                    assert result is not None

    asyncio.run(both())
