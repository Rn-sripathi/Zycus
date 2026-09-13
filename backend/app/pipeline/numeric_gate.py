"""Pipeline step 3: deterministic numeric check.

This runs BEFORE the model, not as a tool the model chooses to call. When it
produces a verdict, that verdict is arithmetic -- "7 days < 30 days required" --
and involves no model judgment at all. That is what makes the HIGH confidence
tier honest rather than a repackaged model self-report.

The hard part is not the comparison, it is picking the *right* number. Clause 1
of the sample contract contains four quantities (12 months, 12-month, 10 days,
7 days) governed by two different rules, so each number must be tied back to the
rule it actually belongs to via the rule's anchor phrases.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.domain.models import (
    Clause,
    Comparison,
    GateResult,
    NumericEvidence,
    Rule,
    RuleType,
    Unit,
)

_NUMBER_WORDS: dict[str, int] = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
    "fifteen": 15, "twenty": 20, "thirty": 30, "forty": 40, "forty-five": 45,
    "sixty": 60, "ninety": 90,
}

# "10 days" / "7 days'" / "12-month" / "THREE (3) MONTHS" / "fifteen (15) days"
_QUANTITY = re.compile(
    r"(?P<num>\d+|[A-Za-z]+)"
    r"(?:\s*\(\s*(?P<paren>\d+)\s*\))?"
    r"[\s\-]*"
    r"(?P<unit>days?|months?)\b",
    re.IGNORECASE,
)

_EXCERPT_PADDING = 45


@dataclass(frozen=True)
class Quantity:
    """A number plus its unit, located in the clause text."""

    value: float
    unit: Unit
    start: int
    end: int
    excerpt: str


def extract_quantities(text: str) -> list[Quantity]:
    """Find every number-with-unit in ``text``, in order of appearance.

    Numbers we cannot resolve (e.g. "per month", "several days") are skipped
    rather than guessed at.
    """
    quantities: list[Quantity] = []

    for match in _QUANTITY.finditer(text):
        value = _resolve_value(match.group("num"), match.group("paren"))
        if value is None:
            continue

        unit = Unit.DAYS if match.group("unit").lower().startswith("day") else Unit.MONTHS
        quantities.append(
            Quantity(
                value=value,
                unit=unit,
                start=match.start(),
                end=match.end(),
                excerpt=_excerpt(text, match.start(), match.end()),
            )
        )

    return quantities


def evaluate_numeric_rule(clause: Clause, rule: Rule) -> NumericEvidence:
    """Check ``clause`` against a numeric ``rule`` without involving the model."""
    if rule.rule_type is not RuleType.NUMERIC:
        raise ValueError(f"{rule.id} is not a numeric rule")
    if rule.threshold is None or rule.unit is None or rule.comparison is None:
        raise ValueError(f"{rule.id} is missing threshold, unit or comparison")

    text = clause.full_text
    candidates = [q for q in extract_quantities(text) if q.unit is rule.unit]

    if not candidates:
        return NumericEvidence(
            result=GateResult.NOT_EXTRACTABLE,
            threshold=rule.threshold,
            unit=rule.unit,
            explanation=(
                f"No value in {rule.unit.value} found in this clause, so the rule could "
                "not be checked arithmetically."
            ),
        )

    chosen = _select_candidate(text, candidates, rule)
    if chosen is None:
        return NumericEvidence(
            result=GateResult.NOT_EXTRACTABLE,
            threshold=rule.threshold,
            unit=rule.unit,
            explanation=(
                f"Found {len(candidates)} different values in {rule.unit.value} and none "
                "could be tied to this rule with confidence."
            ),
        )

    violated = _is_violation(chosen.value, rule.threshold, rule.comparison)
    requirement = "at least" if rule.comparison is Comparison.AT_LEAST else "at most"
    comparator = "<" if rule.comparison is Comparison.AT_LEAST else ">"

    explanation = (
        f"Found {_fmt(chosen.value)} {rule.unit.value}; playbook requires {requirement} "
        f"{_fmt(rule.threshold)} {rule.unit.value}. "
        + (
            f"{_fmt(chosen.value)} {comparator} {_fmt(rule.threshold)}, so the clause fails the rule."
            if violated
            else f"The clause meets the rule."
        )
    )

    return NumericEvidence(
        result=GateResult.VERIFIED_VIOLATION if violated else GateResult.VERIFIED_COMPLIANT,
        found_value=chosen.value,
        threshold=rule.threshold,
        unit=rule.unit,
        excerpt=chosen.excerpt,
        explanation=explanation,
    )


def _select_candidate(text: str, candidates: list[Quantity], rule: Rule) -> Quantity | None:
    """Pick the quantity that belongs to ``rule``.

    Uses the rule's anchor phrases: the winning number is the one sitting closest
    to a phrase that identifies this rule's subject matter. With no anchor match
    we only proceed when there is a single candidate -- otherwise we would be
    guessing, and guessing is exactly what the LLM fall-through is for.
    """
    if len(candidates) == 1:
        return candidates[0]

    anchor_positions = _anchor_positions(text, rule.anchors)
    if not anchor_positions:
        return None

    def distance(candidate: Quantity) -> int:
        return min(abs(candidate.start - position) for position in anchor_positions)

    return min(candidates, key=distance)


def _anchor_positions(text: str, anchors: tuple[str, ...]) -> list[int]:
    lowered = text.lower()
    positions: list[int] = []

    for anchor in anchors:
        needle = anchor.lower()
        start = lowered.find(needle)
        while start != -1:
            positions.append(start)
            start = lowered.find(needle, start + 1)

    return positions


def _resolve_value(raw_number: str, parenthetical: str | None) -> float | None:
    # "THREE (3)" -- prefer the digits, they are unambiguous.
    if parenthetical:
        return float(parenthetical)
    if raw_number.isdigit():
        return float(raw_number)
    return _NUMBER_WORDS.get(raw_number.lower())


def _is_violation(value: float, threshold: float, comparison: Comparison) -> bool:
    if comparison is Comparison.AT_LEAST:
        return value < threshold
    return value > threshold


def _excerpt(text: str, start: int, end: int) -> str:
    left = max(0, start - _EXCERPT_PADDING)
    right = min(len(text), end + _EXCERPT_PADDING)
    snippet = " ".join(text[left:right].split())
    prefix = "..." if left > 0 else ""
    suffix = "..." if right < len(text) else ""
    return f"{prefix}{snippet}{suffix}"


def _fmt(value: float) -> str:
    return str(int(value)) if float(value).is_integer() else str(value)
