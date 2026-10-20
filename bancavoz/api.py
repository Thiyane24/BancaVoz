from __future__ import annotations

import os
import re
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .db import Database
from .digest import bedrock_digest, digest_facts, render_digest
from .service import LedgerService

app = FastAPI(title="BancaVoz")
STATIC_DIR = Path(__file__).parent / "web"
service = LedgerService(
    Database(os.getenv("BANCAVOZ_DATABASE_URL", "sqlite:///./bancavoz.db")),
    os.getenv("BANCAVOZ_CURRENCY", "MZN"),
)

MCP_TOOLS = [
    {"name": "log_sale", "description": "Log a sale.", "inputSchema": {"type": "object"}},
    {"name": "log_expense", "description": "Log an expense.", "inputSchema": {"type": "object"}},
    {"name": "record_credit_payment", "description": "Record a customer payment.", "inputSchema": {"type": "object"}},
    {"name": "get_credit_owed", "description": "List customer balances.", "inputSchema": {"type": "object"}},
    {"name": "get_daily_summary", "description": "Summarize the ledger.", "inputSchema": {"type": "object"}},
    {"name": "undo_last_entry", "description": "Reverse a ledger entry.", "inputSchema": {"type": "object"}},
]


def auth(authorization: Annotated[str | None, Header()] = None) -> str:
    expected = os.getenv("BANCAVOZ_BEARER_TOKEN", "dev-token")
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "missing bearer token")
    if authorization.removeprefix("Bearer ").strip() != expected:
        raise HTTPException(401, "invalid bearer token")
    return "merchant"


class Transaction(BaseModel):
    amount: float | None = None
    unit_price: float | None = None
    amount_paid: float | None = None
    idempotency_key: str = ""
    product: str | None = None
    quantity: int = 1
    party: str | None = None


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/mcp-legacy")
async def mcp_endpoint(request: Request, merchant: str = Depends(auth)):
    """Small JSON-RPC MCP surface; the optional official SDK can replace this in deployment."""
    message = await request.json()
    method = message.get("method")
    request_id = message.get("id")
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": request_id, "result": {"tools": MCP_TOOLS}}
    if method != "tools/call":
        return {"jsonrpc": "2.0", "id": request_id,
                "error": {"code": -32601, "message": "method not found"}}
    params = message.get("params", {})
    name, args = params.get("name"), params.get("arguments", {})
    try:
        if name == "log_sale":
            entry = service.sale(merchant, args.get("amount"),
                                 idempotency_key=args["idempotency_key"], product=args["item"],
                                 quantity=args.get("quantity", 1), party=args.get("customer"),
                                 unit_price=args.get("unit_price"), amount_paid=args.get("amount_paid"))
            result = {"speech": "Sale logged.", "data": entry.as_dict()}
        elif name == "log_expense":
            entry = service.expense(merchant, args["amount"], idempotency_key=args["idempotency_key"],
                                    category=args.get("category", "other"), description=args["description"])
            result = {"speech": "Expense logged.", "data": entry.as_dict()}
        elif name == "get_daily_summary":
            result = {"speech": "Daily summary ready.", "data": service.summary(merchant)}
        elif name == "get_credit_owed":
            result = {"speech": "Credit balances ready.", "data": service.credit_balances(merchant)}
        elif name == "undo_last_entry":
            entry = service.undo_last(merchant, idempotency_key=args["idempotency_key"])
            result = {"speech": "Last entry undone.", "data": entry.as_dict()}
        elif name == "record_credit_payment":
            entry = service.payment(merchant, args["amount"], idempotency_key=args["idempotency_key"],
                                    party=args["customer"])
            result = {"speech": "Payment recorded.", "data": entry.as_dict()}
        else:
            raise ValueError(f"unknown tool: {name}")
        return {"jsonrpc": "2.0", "id": request_id, "result": {"content": [{"type": "text", "text": result}]}}
    except (KeyError, ValueError) as exc:
        return {"jsonrpc": "2.0", "id": request_id,
                "error": {"code": -32602, "message": str(exc)}}


@app.post("/sales")
def sales(body: Transaction, merchant: str = Depends(auth)):
    if not body.idempotency_key:
        raise HTTPException(422, "idempotency_key is required")
    try:
        return service.sale(merchant, body.amount, idempotency_key=body.idempotency_key,
                            product=body.product, quantity=body.quantity, party=body.party,
                            unit_price=body.unit_price, amount_paid=body.amount_paid).as_dict()
    except ValueError as exc:
        raise HTTPException(409 if "idempotency" in str(exc) else 422, str(exc))


@app.post("/expenses")
def expenses(body: Transaction, merchant: str = Depends(auth)):
    try:
        return service.expense(merchant, body.amount, idempotency_key=body.idempotency_key,
                               category=body.product or "expense").as_dict()
    except ValueError as exc:
        raise HTTPException(409 if "different request" in str(exc) else 422, str(exc))


@app.post("/credits")
def credits(body: Transaction, merchant: str = Depends(auth)):
    if not body.party:
        raise HTTPException(422, "party is required")
    if not body.idempotency_key:
        raise HTTPException(422, "idempotency_key is required")
    return service.credit(merchant, body.amount, idempotency_key=body.idempotency_key,
                          party=body.party).as_dict()


@app.post("/payments")
def payments(body: Transaction, merchant: str = Depends(auth)):
    if not body.party:
        raise HTTPException(422, "party is required")
    if not body.idempotency_key:
        raise HTTPException(422, "idempotency_key is required")
    return service.payment(merchant, body.amount, idempotency_key=body.idempotency_key,
                           party=body.party).as_dict()


@app.post("/undo")
def undo(merchant: str = Depends(auth)):
    return service.undo_last(merchant, idempotency_key=f"http-undo:{merchant}").as_dict()


@app.get("/summary")
def summary(day: str | None = Query(None), timezone: str = Query("UTC"),
            merchant: str = Depends(auth)):
    try:
        facts = digest_facts(service.summary(merchant, day=day, timezone_name=timezone),
                             service.top_sellers(merchant, day=day, timezone_name=timezone))
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    return facts | {"digest": bedrock_digest(facts, service.currency) or render_digest(facts, service.currency)}


@app.get("/stock")
def stock(low_stock: bool = Query(False), merchant: str = Depends(auth)):
    return service.stock(merchant, low_stock=low_stock)


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


@app.post("/sim/utterance")
async def sim_utterance(body: dict[str, str]) -> dict:
    text = body.get("utterance", "").strip()
    lowered = text.lower()
    calls: list[dict] = []
    sale_match = re.search(r"sold\s+(\d+)\s+(.+?)\s+(?:at|for)\s+([\d.]+)", lowered)
    if sale_match:
        quantity, item, price = int(sale_match.group(1)), sale_match.group(2).strip(), float(sale_match.group(3))
        result = service.sale("demo", price * quantity, idempotency_key=f"sim-sale:{text}",
                              product=item, quantity=quantity)
        calls.append({"tool": "log_sale", "arguments": {"item": item, "quantity": quantity,
                                                         "unit_price": price}})
        return {"speech": f"Logged {quantity} {item}.", "data": result.as_dict(), "tool_calls": calls}
    expense_match = re.search(r"(?:spent|expense).*?([\d.]+)", lowered)
    if expense_match:
        amount = float(expense_match.group(1))
        result = service.expense("demo", amount, idempotency_key=f"sim-expense:{text}")
        calls.append({"tool": "log_expense", "arguments": {"amount": amount}})
        return {"speech": "Expense logged.", "data": result.as_dict(), "tool_calls": calls}
    if "paid" in lowered or "payment" in lowered:
        payment_match = re.search(r"(?:paid|payment).*?([\d.]+)", lowered)
        if payment_match:
            amount = float(payment_match.group(1))
            customer = "Maria"
            result = service.payment("demo", amount, idempotency_key=f"sim-payment:{text}", party=customer)
            calls.append({"tool": "record_credit_payment", "arguments": {"customer": customer, "amount": amount}})
            return {"speech": f"{customer} payment recorded.", "data": result.as_dict(), "tool_calls": calls}
    if "undo" in lowered or "oops" in lowered:
        result = service.undo_last("demo", idempotency_key=f"sim-undo:{text}")
        calls.append({"tool": "undo_last_entry", "arguments": {}})
        return {"speech": "Last entry undone.", "data": result.as_dict(), "tool_calls": calls}
    if "summary" in lowered or "how did" in lowered:
        calls.append({"tool": "get_daily_summary", "arguments": {}})
        facts = digest_facts(service.summary("demo"), service.top_sellers("demo"))
        return {"speech": render_digest(facts, service.currency), "data": facts, "tool_calls": calls}
    return {"speech": "Try saying sold, spent, or summary.", "data": {"needs_clarification": True},
            "tool_calls": calls}


@app.post("/simulator", response_class=HTMLResponse)
async def simulator_post(request: Request):
    form = await request.form()
    result = await sim_utterance({"utterance": str(form.get("utterance", ""))})
    return f"<p>{result['speech']}</p><pre>{result['data']}</pre><a href='/sim'>Again</a>"


def create_app() -> FastAPI:
    return app


def _mount_official_mcp() -> None:
    try:
        from starlette.types import Receive, Scope, Send

        from .mcp_server import build_mcp
    except ImportError:
        return

    sdk_app = build_mcp(service, "merchant").streamable_http_app()

    @asynccontextmanager
    async def lifespan(_app):
        async with sdk_app.router.lifespan_context(sdk_app):
            yield

    app.router.lifespan_context = lifespan

    async def authenticated(scope: Scope, receive: Receive, send: Send) -> None:
        headers = {key.decode().lower(): value.decode() for key, value in scope.get("headers", [])}
        expected = os.getenv("BANCAVOZ_BEARER_TOKEN", "dev-token")
        if headers.get("authorization") != f"Bearer {expected}":
            from starlette.responses import JSONResponse
            response = JSONResponse({"detail": "invalid bearer token"}, status_code=401)
            await response(scope, receive, send)
            return
        await sdk_app(scope, receive, send)

    app.mount("/mcp", authenticated)


_mount_official_mcp()


app.mount("/assets", StaticFiles(directory=STATIC_DIR / "static"), name="assets")


@app.get("/", response_class=HTMLResponse)
def landing_page() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/app", response_class=HTMLResponse)
def merchant_console() -> FileResponse:
    return FileResponse(STATIC_DIR / "app.html")
