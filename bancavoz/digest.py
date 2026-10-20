from __future__ import annotations

import os
from typing import Any


def digest_facts(summary: dict[str, Any], top_sellers: list[dict[str, Any]]) -> dict[str, Any]:
    return {"net_minor": summary.get("net", 0), "sales_minor": summary.get("sale", 0),
            "expenses_minor": summary.get("expense", 0), "top_sellers": top_sellers}


def render_digest(facts: dict[str, Any], currency: str = "MZN") -> str:
    def money(n: int) -> str:
        return f"{currency} {n / 100:.2f}"
    sellers = ", ".join(f"{x['product']} ({x['sold']})" for x in facts["top_sellers"]) or "none yet"
    return (f"Sales: {money(facts['sales_minor'])}. Expenses: {money(facts['expenses_minor'])}. "
            f"Net: {money(facts['net_minor'])}. Top sellers: {sellers}.")


def bedrock_digest(facts: dict[str, Any], currency: str = "MZN") -> str | None:
    model_id = os.getenv("BANCAVOZ_BEDROCK_MODEL_ID")
    if not model_id:
        return None
    try:
        import boto3
        body = {"inputText": render_digest(facts, currency), "textGenerationConfig": {"maxTokenCount": 120}}
        response = boto3.client("bedrock-runtime", region_name=os.getenv("AWS_REGION", "ap-south-1")).invoke_model(
            modelId=model_id, body=__import__("json").dumps(body))
        return response["body"].read().decode()
    except Exception:
        return None
