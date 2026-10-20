from __future__ import annotations

import json
import os
from functools import lru_cache
from typing import Any


def _minor(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError("digest facts must contain integer minor-unit values")
    return value


def digest_facts(summary: dict[str, Any], top_sellers: list[dict[str, Any]],
                 previous: dict[str, Any] | None = None) -> dict[str, Any]:
    sellers = []
    for seller in top_sellers:
        sellers.append({"product": str(seller.get("product", "")), "sold": _minor(seller.get("sold", 0))})
    facts = {
        "net_minor": _minor(summary.get("profit", 0)),
        "sales_minor": _minor(summary.get("sales", 0)),
        "expenses_minor": _minor(summary.get("expenses", 0)),
        "credit_given_minor": _minor(summary.get("credit_given", 0)),
        "credit_collected_minor": _minor(summary.get("credit_collected", 0)),
        "entry_count": _minor(summary.get("entry_count", 0)),
        "top_sellers": sellers,
    }
    if previous is not None:
        facts["previous"] = digest_facts(previous, [], None)
    return facts


@lru_cache(maxsize=256)
def _render_cached(serialized: str, currency: str) -> str:
    facts = json.loads(serialized)
    def money(n: int) -> str:
        return f"{currency} {n / 100:.2f}"
    sellers = ", ".join(f"{x['product']} ({x['sold']})" for x in facts["top_sellers"]) or "none yet"
    return (f"Sales: {money(facts['sales_minor'])}. Expenses: {money(facts['expenses_minor'])}. "
            f"Net: {money(facts['net_minor'])}. Top sellers: {sellers}.")


def render_digest(facts: dict[str, Any], currency: str = "MZN") -> str:
    return _render_cached(json.dumps(facts, sort_keys=True), currency)


def bedrock_digest(facts: dict[str, Any], currency: str = "MZN") -> str | None:
    model_id = os.getenv("BANCAVOZ_BEDROCK_MODEL_ID")
    if not model_id:
        return None
    try:
        import boto3  # type: ignore[import-not-found]
        body = {"inputText": render_digest(facts, currency), "textGenerationConfig": {"maxTokenCount": 120}}
        response = boto3.client("bedrock-runtime", region_name=os.getenv("AWS_REGION", "ap-south-1")).invoke_model(
            modelId=model_id, body=__import__("json").dumps(body))
        return response["body"].read().decode()
    except (ImportError, KeyError, OSError, TypeError, ValueError):
        return None
