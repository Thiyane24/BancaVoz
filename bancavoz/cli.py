from __future__ import annotations

import os

from .db import Database


def migrate() -> None:
    """Apply database schema migrations and bootstrap the configured merchant."""
    db = Database(os.getenv("BANCAVOZ_DATABASE_URL", "sqlite:///./bancavoz.db"))
    db.migrations()
    token = os.getenv("BANCAVOZ_BEARER_TOKEN")
    if token:
        db.ensure_merchant(os.getenv("BANCAVOZ_MERCHANT_ID", "merchant"), token)
    db.close()


def main() -> None:
    migrate()


if __name__ == "__main__":
    main()
