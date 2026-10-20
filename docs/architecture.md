# Architecture

`LedgerService` owns business rules and integer minor-unit money. `Database` owns
connection, transactions, and schema. `api.py` is a thin FastAPI adapter with
bearer authentication and merchant scoping. Ledger rows are append-only; undo is
represented as a compensating row rather than mutation. Digest facts are separated
from rendering so Bedrock can be added without changing accounting behavior.
