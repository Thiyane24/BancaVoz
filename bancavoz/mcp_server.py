"""Official MCP SDK tool registration, kept import-safe when the extra is absent."""
from .service import LedgerService


def build_mcp(service: LedgerService):
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError:
        return None

    mcp = FastMCP("bancavoz")

    @mcp.tool()
    def log_sale(merchant_id: str, item: str, quantity: int, unit_price: float,
                 idempotency_key: str, customer: str = "") -> dict:
        entry = service.sale(merchant_id, unit_price * quantity, idempotency_key=idempotency_key,
                             product=item, quantity=quantity, party=customer or None)
        return {"speech": f"Logged {quantity} {item}.", "data": entry.as_dict()}

    @mcp.tool()
    def log_expense(merchant_id: str, description: str, amount: float,
                    idempotency_key: str, category: str = "other") -> dict:
        entry = service.expense(merchant_id, amount, idempotency_key=idempotency_key,
                                category=category, description=description)
        return {"speech": "Expense logged.", "data": entry.as_dict()}

    @mcp.tool()
    def get_daily_summary(merchant_id: str) -> dict:
        return {"speech": "Daily summary ready.", "data": service.summary(merchant_id)}

    @mcp.tool()
    def record_credit_payment(merchant_id: str, customer: str, amount: float,
                              idempotency_key: str) -> dict:
        entry = service.payment(merchant_id, amount, idempotency_key=idempotency_key, party=customer)
        return {"speech": f"{customer} payment recorded.", "data": entry.as_dict()}

    @mcp.tool()
    def get_credit_owed(merchant_id: str) -> dict:
        balances: dict[str, int] = {}
        for entry in service.list_entries(merchant_id):
            if entry.party and entry.entry_type in ("credit", "payment"):
                delta = entry.amount_minor if entry.entry_type == "credit" else -entry.amount_minor
                balances[entry.party] = balances.get(entry.party, 0) + delta
        return {"speech": "Credit balances ready.", "data": balances}

    @mcp.tool()
    def undo_last_entry(merchant_id: str, entry_id: int, idempotency_key: str) -> dict:
        entry = service.undo(merchant_id, entry_id, idempotency_key=idempotency_key)
        return {"speech": "Entry undone.", "data": entry.as_dict()}

    return mcp
