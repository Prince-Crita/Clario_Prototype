from __future__ import annotations

import json
from decimal import Decimal
from typing import Any

import pytest

from clario.core.money import (
    format_inr,
    format_inr_compact,
    format_percent,
    percent_change,
    ratio_percent,
    round_half_up,
    to_decimal,
)
from clario.settings import REPO_ROOT

VECTORS: dict[str, Any] = json.loads(
    (REPO_ROOT / "contracts" / "money-format-vectors.json").read_text(encoding="utf-8")
)


@pytest.mark.parametrize("case", VECTORS["money"], ids=lambda c: f"{c['value']}/{c['decimals']}")
def test_money_vectors(case: dict[str, Any]) -> None:
    value = Decimal(case["value"])
    assert format_inr(value, decimals=case["decimals"]) == case["full"]
    assert format_inr_compact(value) == case["compact"]


@pytest.mark.parametrize("case", VECTORS["percent"], ids=lambda c: str(c["value"]))
def test_percent_vectors(case: dict[str, Any]) -> None:
    value = None if case["value"] is None else Decimal(case["value"])
    assert format_percent(value, decimals=case["decimals"]) == case["text"]


def test_to_decimal_refuses_float() -> None:
    with pytest.raises(TypeError, match="parse_float"):
        to_decimal(0.1)  # type: ignore[arg-type]


def test_to_decimal_accepts_strings_ints_and_empty() -> None:
    assert to_decimal("3000.0") == Decimal("3000.0")
    assert to_decimal(5) == Decimal(5)
    assert to_decimal(None) == Decimal(0)
    assert to_decimal("") == Decimal(0)
    with pytest.raises(ValueError, match="not a decimal"):
        to_decimal("abc")


def test_round_half_up() -> None:
    assert round_half_up(Decimal("2.345")) == Decimal("2.35")
    assert round_half_up(Decimal("-2.345")) == Decimal("-2.35")


def test_percent_change_and_ratio() -> None:
    assert percent_change(Decimal(110), Decimal(100)) == Decimal(10)
    assert percent_change(Decimal(-50), Decimal(-100)) == Decimal(50)
    assert percent_change(Decimal(1), Decimal(0)) is None
    assert ratio_percent(Decimal(1), Decimal(0)) is None
    # Director PDF identity: 8,37,581 ÷ 8,95,675 → 94% of billed
    ratio = ratio_percent(Decimal(837581), Decimal(895675))
    assert format_percent(ratio) == "94%"
