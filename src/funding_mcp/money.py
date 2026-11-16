"""Exact USD money handling (R-15). Money is integer cents everywhere; floats are never used."""

import re
from decimal import Decimal

from .errors import InvalidInput

MAX_AMOUNT_CENTS = 100_000_000  # 1,000,000.00 USD (SPEC A-1)
AMOUNT_PATTERN = r"^(0|[1-9][0-9]{0,6})(\.[0-9]{1,2})?$"
_AMOUNT_RE = re.compile(AMOUNT_PATTERN)


def parse_amount(text: object, field: str = "amount") -> int:
    """Parse a positive USD decimal string such as "300" or "300.50" into integer cents."""
    if not isinstance(text, str) or not _AMOUNT_RE.fullmatch(text):
        raise InvalidInput(f'{field} must be a USD string with at most 2 decimals, e.g. "300.00"', [field])
    cents = int(Decimal(text) * 100)  # exact: Decimal of a validated literal, scaled by 100
    if cents <= 0 or cents > MAX_AMOUNT_CENTS:
        raise InvalidInput(f"{field} must be greater than 0.00 and at most 1000000.00", [field])
    return cents


def format_cents(cents: int) -> str:
    if cents < 0:
        raise ValueError("money amounts are never negative")
    return f"{cents // 100}.{cents % 100:02d}"


def money(cents: int) -> dict[str, int | str]:
    """Output shape for every money value (SPEC §5.1 Money)."""
    return {"cents": cents, "usd": format_cents(cents)}
