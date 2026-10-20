from pathlib import Path


def test_compose_defines_healthy_postgres_dependency_and_app_probe():
    compose = Path("docker-compose.yml").read_text(encoding="utf-8")
    assert "postgres:" in compose
    assert "pg_isready" in compose
    assert "condition: service_healthy" in compose
    assert "env_file:" in compose and "required: false" in compose
    assert "BANCAVOZ_DATABASE_URL" in compose
    assert "localhost:8000/healthz" in compose
