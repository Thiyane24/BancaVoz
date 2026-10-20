from __future__ import annotations

import hmac
import os
import re
import uuid
from contextlib import asynccontextmanager
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Annotated, TypedDict

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, field_validator

from .db import Database
from .digest import digest_facts, render_digest
from .service import LedgerService

app = FastAPI(title="BancaVoz")
STATIC_DIR = Path(__file__).parent / "web"
service = LedgerService(
    Database(os.getenv("BANCAVOZ_DATABASE_URL", "sqlite:///./bancavoz.db")),
    os.getenv("BANCAVOZ_CURRENCY", "MZN"),
)


async def domain_error(_request: Request, exc: Exception):
    return __import__("fastapi").responses.JSONResponse(
        {"detail": str(exc)}, status_code=422
    )


for _error_type in (ValueError, KeyError, InvalidOperation):
    app.add_exception_handler(_error_type, domain_error)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'"
    response.headers["X-Request-ID"] = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    return response

MCP_TOOLS = [
    {"name": "log_sale", "description": "Log a sale.", "inputSchema": {"type": "object"}},
    {"name": "log_expense", "description": "Log an expense.", "inputSchema": {"type": "object"}},
    {"name": "record_credit_payment", "description": "Record a customer payment.", "inputSchema": {"type": "object"}},
    {"name": "get_credit_owed", "description": "List customer balances.", "inputSchema": {"type": "object"}},
    {"name": "get_daily_summary", "description": "Summarize the ledger.", "inputSchema": {"type": "object"}},
    {"name": "undo_last_entry", "description": "Reverse a ledger entry.", "inputSchema": {"type": "object"}},
]

class DemoSaleContext(TypedDict):
    entry_id: int
    item: str
    quantity: int
    unit_price: Decimal


_demo_sale_context: dict[str, DemoSaleContext] = {}


def auth(request: Request, authorization: Annotated[str | None, Header()] = None) -> str:
    expected = getattr(request.app.state, "bearer_token", os.getenv("BANCAVOZ_BEARER_TOKEN", "dev-token"))
    if os.getenv("BANCAVOZ_ENV", "development") == "production" and expected == "dev-token":
        raise HTTPException(503, "production token is not configured")
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "missing bearer token")
    if not hmac.compare_digest(authorization.removeprefix("Bearer ").strip(), expected):
        raise HTTPException(401, "invalid bearer token")
    return "merchant"


class Transaction(BaseModel):
    amount: Decimal | None = None
    unit_price: Decimal | None = None
    amount_paid: Decimal | None = None
    idempotency_key: str = ""
    product: str | None = None
    quantity: int = 1
    party: str | None = None

    @field_validator("amount", "unit_price", "amount_paid", mode="before")
    @classmethod
    def reject_float_amounts(cls, value):
        if isinstance(value, float):
            raise TypeError("amounts must be decimal strings, not floats")
        return value


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/readyz")
def readyz() -> dict[str, str]:
    service.db.connect()
    return {"status": "ready"}


@app.post("/sales")
def sales(body: Transaction, merchant: str = Depends(auth)):
    try:
        return service.sale(merchant, body.amount, idempotency_key=body.idempotency_key,
                            product=body.product, quantity=body.quantity, party=body.party,
                            unit_price=body.unit_price, amount_paid=body.amount_paid).as_dict()
    except ValueError as exc:
        raise HTTPException(409 if "idempotency" in str(exc) else 422, str(exc))


@app.post("/expenses")
def expenses(body: Transaction, merchant: str = Depends(auth)):
    if body.amount is None:
        raise HTTPException(422, "amount is required")
    try:
        return service.expense(merchant, body.amount, idempotency_key=body.idempotency_key,
                               category=body.product or "expense").as_dict()
    except ValueError as exc:
        raise HTTPException(409 if "different request" in str(exc) else 422, str(exc))


@app.post("/credits")
def credits(body: Transaction, merchant: str = Depends(auth)):
    if body.amount is None:
        raise HTTPException(422, "amount is required")
    if not body.party:
        raise HTTPException(422, "party is required")
    try:
        return service.credit(merchant, body.amount, idempotency_key=body.idempotency_key,
                              party=body.party).as_dict()
    except ValueError as exc:
        raise HTTPException(409 if "different request" in str(exc) else 422, str(exc))


@app.post("/payments")
def payments(body: Transaction, merchant: str = Depends(auth)):
    if body.amount is None:
        raise HTTPException(422, "amount is required")
    if not body.party:
        raise HTTPException(422, "party is required")
    try:
        return service.payment(merchant, body.amount, idempotency_key=body.idempotency_key,
                               party=body.party).as_dict()
    except ValueError as exc:
        raise HTTPException(409 if "different request" in str(exc) else 422, str(exc))


@app.post("/undo")
def undo(merchant: str = Depends(auth)):
    return service.undo_last(merchant, idempotency_key="").as_dict()


@app.get("/summary")
def summary(day: str | None = Query(None), timezone: str = Query("UTC"),
            merchant: str = Depends(auth)):
    try:
        facts = digest_facts(service.summary(merchant, day=day, timezone_name=timezone),
                             service.top_sellers(merchant, day=day, timezone_name=timezone))
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    return facts | {"digest": render_digest(facts, service.currency)}


@app.get("/stock")
def stock(low_stock: bool = Query(False), merchant: str = Depends(auth)):
    return service.stock(merchant, low_stock=low_stock)


@app.get("/entries")
def entries(merchant: str = Depends(auth)):
    return [entry.as_dict() for entry in service.list_entries(merchant)]


@app.get("/credits")
def credits_list(merchant: str = Depends(auth)):
    return service.credit_balances(merchant)


class Command(BaseModel):
    utterance: str


class StockUpdate(BaseModel):
    product: str
    quantity: int
    low_stock_threshold: int = 0


@app.post("/stock")
def set_stock(body: StockUpdate, merchant: str = Depends(auth)):
    try:
        return service.set_stock(merchant, body.product, body.quantity, body.low_stock_threshold)
    except ValueError as exc:
        raise HTTPException(422, str(exc))


@app.get("/top-sellers")
def top_sellers(day: str | None = Query(None), timezone: str = Query("UTC"),
                merchant: str = Depends(auth)):
    try:
        return service.top_sellers(merchant, day=day, timezone_name=timezone)
    except ValueError as exc:
        raise HTTPException(422, str(exc))


@app.get("/sim", response_class=HTMLResponse)
@app.get("/simulator", response_class=HTMLResponse)
def simulator() -> FileResponse:
    return FileResponse(STATIC_DIR / "sim.html")


def _parse_command(text: str, merchant: str) -> dict:
    text = text.strip()
    lowered = text.lower()
    calls: list[dict] = []
    sale_match = re.search(r"sold\s+(\d+)\s+(.+?)\s+(?:at|for)\s+([\d.]+)", lowered)
    if sale_match:
        quantity, item, price = int(sale_match.group(1)), sale_match.group(2).strip(), float(sale_match.group(3))
        result = service.sale(merchant, unit_price=price, idempotency_key=f"sim-sale:{text}",
                              product=item, quantity=quantity)
        _demo_sale_context[merchant] = {
            "entry_id": result.id, "item": item, "quantity": quantity, "unit_price": Decimal(sale_match.group(3))
        }
        calls.append({"tool": "log_sale", "arguments": {"item": item, "quantity": quantity,
                                                         "unit_price": price}})
        return {"speech": f"Logged {quantity} {item}.", "data": result.as_dict(), "tool_calls": calls}
    owes_match = re.search(r"^(.+?)\s+owes\s+half$", lowered)
    if owes_match and merchant in _demo_sale_context:
        context = _demo_sale_context[merchant]
        customer = owes_match.group(1).strip().title()
        service.undo(merchant, int(context["entry_id"]), idempotency_key=f"sim-revise:{text}")
        result = service.sale(
            merchant,
            unit_price=context["unit_price"],
            quantity=int(context["quantity"]),
            customer=customer,
            amount_paid=(context["unit_price"] * int(context["quantity"])) / 2,
            idempotency_key=f"sim-sale-credit:{text}",
            product=str(context["item"]),
        )
        calls.append({"tool": "log_sale", "arguments": {"item": context["item"], "quantity": context["quantity"],
                                                         "unit_price": context["unit_price"], "customer": customer,
                                                         "amount_paid": (context["unit_price"] * int(context["quantity"])) / 2}})
        return {"speech": f"{customer} owes half.", "data": result.as_dict(), "tool_calls": calls}
    expense_match = re.search(r"(?:spent|expense).*?([\d.]+)", lowered)
    if expense_match:
        amount = Decimal(expense_match.group(1))
        category_match = re.search(r"\bon\s+(.+)$", lowered)
        category = category_match.group(1).strip() if category_match else "expense"
        result = service.expense(merchant, amount, idempotency_key=f"sim-expense:{text}", category=category)
        calls.append({"tool": "log_expense", "arguments": {"amount": amount, "category": category}})
        return {"speech": "Expense logged.", "data": result.as_dict(), "tool_calls": calls}
    if "paid" in lowered or "payment" in lowered:
        payment_match = re.search(r"(?:paid|payment).*?([\d.]+)", lowered)
        if payment_match:
            amount = Decimal(payment_match.group(1))
            customer = "Maria"
            result = service.payment(merchant, amount, idempotency_key=f"sim-payment:{text}", party=customer)
            calls.append({"tool": "record_credit_payment", "arguments": {"customer": customer, "amount": amount}})
            return {"speech": f"{customer} payment recorded.", "data": result.as_dict(), "tool_calls": calls}
    if "undo" in lowered or "oops" in lowered:
        result = service.undo_last(merchant, idempotency_key=f"sim-undo:{text}")
        calls.append({"tool": "undo_last_entry", "arguments": {}})
        return {"speech": "Last entry undone.", "data": result.as_dict(), "tool_calls": calls}
    if "summary" in lowered or "how did" in lowered:
        calls.append({"tool": "get_daily_summary", "arguments": {}})
        facts = digest_facts(service.summary(merchant), service.top_sellers(merchant))
        return {"speech": render_digest(facts, service.currency), "data": facts, "tool_calls": calls}
    if "digest" in lowered:
        calls.append({"tool": "get_daily_digest", "arguments": {}})
        facts = digest_facts(service.summary(merchant), service.top_sellers(merchant))
        return {"speech": render_digest(facts, service.currency), "data": facts, "tool_calls": calls}
    return {"speech": "Try saying sold, spent, or summary.", "data": {"needs_clarification": True},
            "tool_calls": calls}


@app.post("/sim/utterance")
async def sim_utterance(body: dict[str, str]) -> dict:
    try:
        return _parse_command(body.get("utterance", ""), "demo")
    except (KeyError, ValueError, InvalidOperation) as exc:
        return {"speech": str(exc), "data": {"error": str(exc)}, "tool_calls": []}


@app.post("/command")
def command(body: Command, merchant: str = Depends(auth)) -> dict:
    try:
        return _parse_command(body.utterance, merchant)
    except (KeyError, ValueError, InvalidOperation) as exc:
        return {"speech": str(exc), "data": {"error": str(exc)}, "tool_calls": []}


def create_app(settings: dict[str, str] | None = None) -> FastAPI:
    global service
    settings = settings or {}
    service = LedgerService(
        Database(settings.get("database_url", os.getenv("BANCAVOZ_DATABASE_URL", "sqlite:///./bancavoz.db"))),
        settings.get("currency", os.getenv("BANCAVOZ_CURRENCY", "MZN")),
    )
    app.state.service = service
    app.state.bearer_token = settings.get("bearer_token", os.getenv("BANCAVOZ_BEARER_TOKEN", "dev-token"))
    app.router.routes = [
        route for route in app.router.routes
        if not getattr(route, "path", "").startswith("/mcp")
    ]
    _mount_official_mcp()
    return app


def _mount_official_mcp() -> None:
    from starlette.responses import JSONResponse
    from starlette.types import Receive, Scope, Send

    from .mcp_server import build_mcp

    sdk_app = build_mcp(service, "merchant").streamable_http_app()

    @asynccontextmanager
    async def lifespan(_app):
        async with sdk_app.router.lifespan_context(sdk_app):
            yield

    app.router.lifespan_context = lifespan

    async def authenticated(scope: Scope, receive: Receive, send: Send) -> None:
        headers = {key.decode().lower(): value.decode() for key, value in scope.get("headers", [])}
        expected = getattr(app.state, "bearer_token", os.getenv("BANCAVOZ_BEARER_TOKEN", "dev-token"))
        provided = headers.get("authorization", "").removeprefix("Bearer ").strip()
        if not provided or not hmac.compare_digest(provided, expected):
            response = JSONResponse({"detail": "invalid bearer token"}, status_code=401)
            await response(scope, receive, send)
            return
        await sdk_app(scope, receive, send)

    app.mount("/mcp", authenticated)
    app.mount("/mcp/", authenticated)


_mount_official_mcp()


app.mount("/assets", StaticFiles(directory=STATIC_DIR / "static"), name="assets")


@app.get("/", response_class=HTMLResponse)
def landing_page() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/app", response_class=HTMLResponse)
def merchant_console() -> FileResponse:
    return FileResponse(STATIC_DIR / "app.html")
