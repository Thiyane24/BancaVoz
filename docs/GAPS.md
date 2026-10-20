# Implementation gaps

- The local default backend is SQLite; Postgres schema and hosting require
  deployment-time validation.
- The dependency-light `/mcp` route is JSON-RPC-compatible but is not a complete
  replacement for SDK-native Streamable HTTP session handling.
- The local demo now covers sale, expense, payment, summary, and undo paths;
  customer names and the full "owes half" language interpretation remain
  simplified for the MVP.
- Bedrock narrative generation is optional; template digest is the deterministic
  fallback.
- Public hosting, external-network smoke testing, Alexa+ registration, and the
  under-three-minute demo video are release activities, not local build steps.
