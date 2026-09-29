"""Grounding guard (plan §21.4): every money and percentage figure in an answer must come from a
tool result in the conversation. In the prototype a mismatch flags the message and is logged (and
fails the evaluation suite); it does not block the answer.

Figures are compared by value after typographic normalisation (Phase 0 found U+2011 hyphens and
narrow no-break spaces in model output): "₹6,48,028", "−₹6,48,028", "₹6.48 lakh", "89%" and
"-89 %" all match the tool value −648028 / −88.95…%. The sign may differ ("a loss of ₹6,48,028").
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any

from clario.core.text import normalise_typography

MONEY = re.compile(
    r"(?:₹|rs\.?|inr)\s*([\d,]+(?:\.\d+)?)\s*(lakh|lac|crore|cr|l|k)?\b", re.IGNORECASE
)
PERCENT = re.compile(r"(\d+(?:\.\d+)?)\s*%")
NUMBER = re.compile(r"-?\d[\d,]*(?:\.\d+)?")
UNITS = {
    "lakh": 100_000,
    "lac": 100_000,
    "l": 100_000,
    "crore": 10_000_000,
    "cr": 10_000_000,
    "k": 1_000,
}


@dataclass(frozen=True, slots=True)
class GroundingReport:
    checked: int
    ungrounded: tuple[str, ...]

    @property
    def grounded(self) -> bool:
        return not self.ungrounded


def _evidence(results: Iterable[Any]) -> set[Decimal]:
    values: set[Decimal] = set()

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)
        elif isinstance(node, bool):
            return
        elif isinstance(node, (int, Decimal)):
            values.add(abs(Decimal(node)))
        elif isinstance(node, float):
            values.add(abs(Decimal(str(node))))
        elif isinstance(node, str):
            for match in NUMBER.findall(normalise_typography(node).replace("−", "-")):
                try:
                    values.add(abs(Decimal(match.replace(",", ""))))
                except InvalidOperation:
                    continue

    for result in results:
        walk(json.loads(result) if isinstance(result, str) else result)
    return values


def _places(text: str) -> int:
    return len(text.split(".")[1]) if "." in text else 0


def _matches(token: Decimal, places: int, evidence: set[Decimal], scale: int = 1) -> bool:
    step = Decimal(1).scaleb(-places)
    for value in evidence:
        if (value / scale).quantize(step, rounding=ROUND_HALF_UP) == token:
            return True
    return False


def check(answer: str, results: Iterable[Any]) -> GroundingReport:
    text = normalise_typography(answer)
    evidence = _evidence(results)
    checked = 0
    ungrounded: list[str] = []
    for match in MONEY.finditer(text):
        raw, unit = match.group(1).replace(",", ""), (match.group(2) or "").lower()
        checked += 1
        try:
            token = Decimal(raw)
        except InvalidOperation:
            continue
        scale = UNITS.get(unit, 1)
        if not _matches(token, _places(raw), evidence, scale):
            ungrounded.append(match.group(0).strip())
    for match in PERCENT.finditer(text):
        raw = match.group(1)
        checked += 1
        if not _matches(Decimal(raw), _places(raw), evidence):
            ungrounded.append(match.group(0).strip())
    return GroundingReport(checked, tuple(ungrounded))
