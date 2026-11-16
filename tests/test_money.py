"""R-15 exact cent arithmetic. AC-18 (invalid amounts), AC-19 (no float drift)."""

import pytest

from funding_mcp.errors import InvalidInput
from funding_mcp.money import MAX_AMOUNT_CENTS, format_cents, money, parse_amount


@pytest.mark.parametrize(
    ("text", "cents"),
    [
        ("300", 30000),
        ("300.5", 30050),
        ("300.00", 30000),
        ("0.01", 1),
        ("0.10", 10),
        ("9700.00", 970000),
        ("1000000.00", MAX_AMOUNT_CENTS),
    ],
)
def test_parse_valid_amounts(text, cents):
    assert parse_amount(text) == cents


@pytest.mark.parametrize(
    "text",
    [
        "0",
        "0.00",
        "-1.00",
        "1.001",
        "abc",
        "1e3",
        " 5",
        "5 ",
        "",
        "01.00",
        "1,000.00",
        "1000000.01",
        "NaN",
        "Infinity",
        ".50",
        "5.",
    ],
)
def test_parse_rejects_invalid_amounts(text):
    with pytest.raises(InvalidInput) as exc:
        parse_amount(text)
    assert exc.value.code == "VALIDATION_ERROR"
    assert exc.value.details["fields"] == ["amount"]


@pytest.mark.parametrize("value", [300, 300.0, None, b"300"])
def test_parse_rejects_non_strings(value):
    with pytest.raises(InvalidInput):
        parse_amount(value)


@pytest.mark.parametrize(
    ("cents", "text"),
    [(0, "0.00"), (5, "0.05"), (10, "0.10"), (30000, "300.00"), (123456789, "1234567.89")],
)
def test_format_cents(cents, text):
    assert format_cents(cents) == text


def test_money_object_shape():
    assert money(970000) == {"cents": 970000, "usd": "9700.00"}


def test_cent_arithmetic_has_no_float_drift():
    # 0.1 + 0.2 != 0.3 in binary floating point; in integer cents it is exact.
    assert 0.1 + 0.2 != 0.3
    assert parse_amount("0.10") + parse_amount("0.20") == parse_amount("0.30") == 30
