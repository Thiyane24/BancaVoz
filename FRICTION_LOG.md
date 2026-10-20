# Friction log

## Real entries

- PostgreSQL was not available for validation; the current adapter rejects
  non-SQLite URLs.
- MCP SDK APIs varied by release, so the project pinned `mcp==1.30.0` and
  validated local `initialize` and `tools/list`.
- The Windows environment lacked IANA timezone data until `tzdata` was added
  and installed.
- The repository secret-pattern scan found no credential-pattern matches, but
  placeholder development-token text remains in example documentation by
  design.

## Missing / blocked

- PostgreSQL adapter, migrations, merchants/digests schema, and CI database job.
- Public deployment URL and rollback evidence.
- Rate limiting, structured JSON logs, and hashed token lookup.
- Complete six-utterance simulator behavior.
- Bedrock Converse, numeric narrative rejection, and persistent digest cache.

Please tell me which missing area should be prioritized next; no additional
friction entries should be invented without command output or a reproducible
test.
