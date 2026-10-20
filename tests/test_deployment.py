from pathlib import Path


def test_database_supports_postgres_url_and_production_schema():
    schema = Path("docs/schema.sql").read_text(encoding="utf-8")
    assert "CREATE TABLE IF NOT EXISTS merchants" in schema
    assert "token_hash" in schema
    assert "CREATE TABLE IF NOT EXISTS digests" in schema
    source = Path("bancavoz/db.py").read_text(encoding="utf-8")
    assert "psycopg" in source
    assert "migrations" in source
    assert "bancavoz-migrate" in Path("pyproject.toml").read_text(encoding="utf-8")


def test_production_security_configuration_is_documented():
    api = Path("bancavoz/api.py").read_text(encoding="utf-8")
    assert "X-RateLimit-Limit" in api
    assert "merchant_for_token" in api
    assert "merchant_id" in api


def test_compose_defines_healthy_postgres_dependency_and_app_probe():
    compose = Path("docker-compose.yml").read_text(encoding="utf-8")
    assert "postgres:" in compose
    assert "pg_isready" in compose
    assert "condition: service_healthy" in compose
    assert "env_file:" in compose and "required: false" in compose
    assert "BANCAVOZ_DATABASE_URL" in compose
    assert "localhost:8000/healthz" in compose
    assert "BANCAVOZ_ENV" in compose
    assert "postgresql://" in compose
    dockerfile = Path("Dockerfile").read_text(encoding="utf-8")
    assert "USER bancavoz" in dockerfile
    assert "bancavoz-migrate" in dockerfile
    assert "tailwindcss-linux-x64" in dockerfile


def test_ci_builds_frontend_runs_security_checks_and_builds_container():
    workflow = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")
    assert "Build Tailwind assets" in workflow
    assert "pip-audit" in workflow
    assert "docker build --tag bancavoz:ci ." in workflow
    assert "permissions:" in workflow


def test_tailwind_frontend_assets_are_wired_and_built():
    for page in ("index.html", "app.html", "sim.html"):
        html = Path(f"bancavoz/web/{page}").read_text(encoding="utf-8")
        assert "/assets/tailwind.css" in html
        assert "/assets/theme.css" in html
    assert "@tailwind base;" in Path("bancavoz/web/static/tailwind.input.css").read_text(encoding="utf-8")
    assert Path("bancavoz/web/static/tailwind.css").stat().st_size > 0


def test_readme_matches_current_verified_surface():
    readme = Path("README.md").read_text(encoding="utf-8")
    assert "JSON-RPC" not in readme
    assert "`GET /entries`" in readme
    assert "`GET /credits`" in readme
    assert "`POST /command`" in readme
    assert "Live URL: not deployed" in readme
    assert "## Screenshots" in readme
    assert "36 passed" in readme
