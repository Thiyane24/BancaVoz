# Security notes

- Never commit `.env`, bearer tokens, AWS credentials, or judge credentials.
- Replace the development bearer token before any public deployment.
- Use HTTPS termination and a hosted secret store.
- Keep merchant identity derived from authentication, not user-provided
  request fields.
- Use parameterized SQL only.
- Treat the current single-token merchant mapping as a prototype limitation.
- Run dependency and secret scans before release.
