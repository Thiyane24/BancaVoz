"""Official MCP SDK tool registration for the authenticated merchant."""
from __future__ import annotations

from decimal import Decimal

from .service import LedgerService


def build_mcp(service: LedgerService, merchant_id: str = "merchant"):
    from mcp.server.fastmcp import FastMCP
    from mcp.server.transport_security import TransportSecuritySettings
    mcp = FastMCP(
        "bancavoz",
        stateless_http=True,
        json_response=True,
        streamable_http_path="/",
        transport_security=TransportSecuritySettings(
            enable_dns_rebinding_protection=False,
        ),
    )

    @mcp.tool(description="Log a sale. Example: sold 3 bags of rice at 450; Maria owes half.")
    def log_sale(item: str, quantity: int = 1, unit_price: Decimal | str = "0",
                 customer: str | None = None, amount_paid: Decimal | str | None = None,
                 idempotency_key: str = "") -> dict:
        entry = service.sale(merchant_id, idempotency_key=idempotency_key, product=item,
                             quantity=quantity, unit_price=unit_price, customer=customer,
                             amount_paid=amount_paid)
        return {"speech": "Sale logged.", "data": entry.as_dict()}

    @mcp.tool(description="Log an expense. Example: spent 200 on transport.")
    def log_expense(description: str, amount: Decimal | str, category: str = "other",
                    idempotency_key: str = "") -> dict:
        entry = service.expense(merchant_id, amount, idempotency_key=idempotency_key,
                                category=category, description=description)
        return {"speech": "Expense logged.", "data": entry.as_dict()}

    @mcp.tool(description="Record a customer payment. Example: Maria paid 300.")
    def record_credit_payment(customer: str, amount: Decimal | str, allow_overpay: bool = False,
                              idempotency_key: str = "") -> dict:
        if allow_overpay:
            raise ValueError("overpayment is disabled in this MVP")
        entry = service.payment(merchant_id, amount, idempotency_key=idempotency_key, party=customer)
        return {"speech": f"{customer} payment recorded.", "data": entry.as_dict()}

    @mcp.tool(description="List credit owed. Example: who owes me?")
    def get_credit_owed(customer: str | None = None) -> dict:
        balances = service.credit_balances(merchant_id)
        if customer:
            from .service import normalize_customer
            return {"speech": "Credit balance ready.", "data": {normalize_customer(customer): balances.get(normalize_customer(customer), 0)}}
        return {"speech": "Credit balances ready.", "data": balances}

    @mcp.tool(description="Get today's summary. Example: how did today go?")
    def get_daily_summary(day: str | None = None) -> dict:
        data = service.summary(merchant_id, day=day, timezone_name="Africa/Maputo")
        return {"speech": "Daily summary ready.", "data": data}

    @mcp.tool(description="Undo the last live entry. Example: undo that.")
    def undo_last_entry(idempotency_key: str = "") -> dict:
        entry = service.undo_last(merchant_id, idempotency_key=idempotency_key)
        return {"speech": "Last entry undone.", "data": entry.as_dict()}

    @mcp.tool(description="Rank top sellers for a day. Example: what sold best?")
    def get_top_sellers(day: str | None = None, limit: int = 3) -> dict:
        return {"speech": "Top sellers ready.", "data": service.top_sellers(
            merchant_id, limit=limit, day=day, timezone_name="Africa/Maputo")}

    @mcp.tool(description="Set item stock. Example: set rice stock to 20.")
    def set_stock(item: str, quantity: int, low_at: int = 0) -> dict:
        return {"speech": "Stock updated.", "data": service.set_stock(merchant_id, item, quantity, low_at)}

    @mcp.tool(description="List low stock items. Example: what is running low?")
    def check_low_stock() -> dict:
        return {"speech": "Low stock ready.", "data": service.stock(merchant_id, low_stock=True)}

    @mcp.tool(description="Get the daily digest. Example: give me my end of day digest.")
    def get_daily_digest(day: str | None = None, refresh: bool = False) -> dict:
        facts = service.summary(merchant_id, day=day, timezone_name="Africa/Maputo")
        return {"speech": "Digest ready.", "data": facts}

    return mcp
