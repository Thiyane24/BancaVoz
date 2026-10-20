# Deployment runbook

1. Copy `.env.example` to `.env`, set a strong bearer token, and configure the
   database URL.
2. Start locally with `docker compose up --build`.
3. Run `docker compose exec bancavoz bancavoz-seed`.
4. Verify `/healthz`, then initialize the official `/mcp` Streamable HTTP
   endpoint with `Authorization: Bearer <token>` and call `tools/list`.
5. Put the service behind an HTTPS reverse proxy before registering it with
   Alexa+.

For a hosted deployment, use a stable HTTPS provider with managed Postgres.
Keep AWS credentials out of the repository; Bedrock is optional because the
simulator and digest template fallback work without it.

The current repository has not been deployed to a public HTTPS host. Do not
claim external reachability, Alexa+ registration, or PostgreSQL production
validation until those checks are run and recorded here.
