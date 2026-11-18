"""Decimal helpers. All financial maths uses Decimal, never float."""
from __future__ import annotations

import re
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

TWO = Decimal("0.01")
ZERO = Decimal("0")


def q2(v: Decimal) -> Decimal:
    return v.quantize(TWO, rounding=ROUND_HALF_UP)


def to_decimal(value) -> Decimal | None:
    """Parse '1,23,456.70', '₹ 1,200', '1200.5' -> Decimal. Returns None if unparseable."""
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    if isinstance(value, (int,)):
        return Decimal(value)
    if isinstance(value, float):
        return Decimal(str(value))
    s = str(value).strip()
    s = re.sub(r"(?i)(rs\.?|inr|₹)", "", s).replace(",", "").replace(" ", "")
    neg = s.startswith("(") and s.endswith(")")
    s = s.strip("()")
    if not s or not re.fullmatch(r"-?\d+(\.\d+)?", s):
        return None
    try:
        d = Decimal(s)
    except InvalidOperation:
        return None
    return -d if neg else d


def fmt(v: Decimal | None) -> str | None:
    return None if v is None else str(q2(v))
