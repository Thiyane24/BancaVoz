from __future__ import annotations

import os
import re
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from .db import Database
from .digest import bedrock_digest, digest_facts, render_digest
from .service import LedgerService

app = FastAPI(title="BancaVoz")
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
    amount: float
    idempotency_key: str = ""
    product: str | None = None
    quantity: int = 1
    party: str | None = None


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/mcp")
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
            entry = service.sale(merchant, args["unit_price"] * args.get("quantity", 1),
                                 idempotency_key=args["idempotency_key"], product=args["item"],
                                 quantity=args.get("quantity", 1), party=args.get("customer"))
            result = {"speech": "Sale logged.", "data": entry.as_dict()}
        elif name == "log_expense":
            entry = service.expense(merchant, args["amount"], idempotency_key=args["idempotency_key"],
                                    category=args.get("category", "other"), description=args["description"])
            result = {"speech": "Expense logged.", "data": entry.as_dict()}
        elif name == "get_daily_summary":
            result = {"speech": "Daily summary ready.", "data": service.summary(merchant)}
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
    return service.sale(merchant, body.amount, idempotency_key=body.idempotency_key,
                        product=body.product, quantity=body.quantity, party=body.party).as_dict()


@app.post("/expenses")
def expenses(body: Transaction, merchant: str = Depends(auth)):
    if not body.idempotency_key:
        raise HTTPException(422, "idempotency_key is required")
    return service.expense(merchant, body.amount, idempotency_key=body.idempotency_key,
                           category=body.product or "expense").as_dict()


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


@app.get("/summary")
def summary(merchant: str = Depends(auth)):
    facts = digest_facts(service.summary(merchant), service.top_sellers(merchant))
    return facts | {"digest": bedrock_digest(facts, service.currency) or render_digest(facts, service.currency)}


@app.get("/stock")
def stock(merchant: str = Depends(auth)):
    return service.stock(merchant)


@app.get("/top-sellers")
def top_sellers(merchant: str = Depends(auth)):
    return service.top_sellers(merchant)


@app.get("/sim", response_class=HTMLResponse)
@app.get("/simulator", response_class=HTMLResponse)
def simulator():
    return """<!doctype html><meta charset="utf-8"><title>BancaVoz simulator</title>
    <h1>Voice simulator</h1><input id="utterance" autofocus>
    <button onclick="send()">Send</button><button onclick="listen()">Mic</button>
    <pre id="result"></pre><script>
    async function send(){const utterance=document.getElementById('utterance').value;
      const r=await fetch('/sim/utterance',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({utterance})}); document.getElementById('result').textContent=JSON.stringify(await r.json(),null,2);}
    function listen(){const S=window.SpeechRecognition||window.webkitSpeechRecognition;if(!S)return;
      const s=new S();s.onresult=e=>{document.getElementById('utterance').value=e.results[0][0].transcript;send()};s.start();}
    </script>"""


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
