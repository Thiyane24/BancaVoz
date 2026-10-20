from __future__ import annotations

from decimal import Decimal


def money_minor(value: int, currency: str = "MZN") -> str:
    return f"{currency} {Decimal(value) / 100:,.2f}"


def sale_logged(total_minor: int, amount_paid_minor: int, customer: str | None,
                currency: str = "MZN") -> str:
    text = f"Logged. {money_minor(total_minor, currency)} total."
    if customer and amount_paid_minor < total_minor:
        text += f" {customer.strip().title()} owes {money_minor(total_minor - amount_paid_minor, currency)}."
    return text
