"""Core domain types.

This module is intentionally dependency-free: no FastAPI, no OpenAI, no I/O.
Everything downstream (pipeline steps, API layer) depends on these types rather
than on each other, which is what keeps each pipeline step unit-testable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class RuleType(str, Enum):
    """How a rule is checked."""

    NUMERIC = "numeric"  # has an extractable number we can compare in Python
    QUALITATIVE = "qualitative"  # requires reading comprehension


class Unit(str, Enum):
    DAYS = "days"
    MONTHS = "months"


class Comparison(str, Enum):
    AT_LEAST = "at_least"  # compliant when actual >= threshold
    AT_MOST = "at_most"  # compliant when actual <= threshold


class Severity(str, Enum):
    """How bad the deviation is. Independent of how sure we are."""

    MINOR = "minor"  # negotiable, would not block a deal on its own
    SERIOUS = "serious"  # escalate to legal / deal-breaker territory


class Tier(str, Enum):
    """How sure we are. Independent of how bad it is."""

    HIGH = "high"  # machine-verified arithmetic, no model judgment involved
    MEDIUM = "medium"  # model found unambiguous quoted evidence
    LOW = "low"  # model was unsure -> hand to a human


class Verdict(str, Enum):
    DEVIATION = "deviation"
    COMPLIANT = "compliant"
    NO_APPLICABLE_RULE = "no_applicable_rule"


class GateResult(str, Enum):
    """Outcome of the deterministic numeric check."""

    VERIFIED_VIOLATION = "verified_violation"
    VERIFIED_COMPLIANT = "verified_compliant"
    NOT_EXTRACTABLE = "not_extractable"  # fall through to the LLM


class EvidenceSource(str, Enum):
    DETERMINISTIC = "deterministic"
    LLM = "llm"


@dataclass(frozen=True)
class Rule:
    """One playbook rule."""

    id: str
    title: str
    text: str  # the rule as written in the playbook
    rationale: str  # the playbook's own "why it matters" text
    rule_type: RuleType
    default_severity: Severity

    # Numeric rules only.
    threshold: float | None = None
    unit: Unit | None = None
    comparison: Comparison | None = None

    # Phrases that tie a particular number to THIS rule. Needed because a single
    # clause can contain several numbers governed by different rules.
    anchors: tuple[str, ...] = ()

    # Fallback keywords, used only if the LLM rule matcher errors out.
    keywords: tuple[str, ...] = ()

    # Guidance handed to the drafting step so redlines sound like the playbook.
    redline_guidance: str = ""


@dataclass(frozen=True)
class Clause:
    number: int
    heading: str
    body: str

    @property
    def full_text(self) -> str:
        return f"{self.number}. {self.heading}. {self.body}".strip()


@dataclass(frozen=True)
class NumericEvidence:
    """Result of the deterministic numeric gate."""

    result: GateResult
    found_value: float | None = None
    threshold: float | None = None
    unit: Unit | None = None
    excerpt: str = ""  # the exact span the number was read from
    explanation: str = ""  # human-readable arithmetic, e.g. "7 days < 30 days required"


@dataclass(frozen=True)
class LLMAssessment:
    """Result of the LLM compliance check."""

    violation: bool
    confidence: float  # model self-reported, 0.0-1.0
    evidence_quote: str
    reasoning: str


@dataclass
class Finding:
    """One (clause, rule) conclusion, as surfaced to the reviewer."""

    clause_number: int
    clause_heading: str
    rule_id: str | None
    rule_title: str | None
    verdict: Verdict
    original_text: str

    tier: Tier | None = None
    severity: Severity | None = None
    auto_suggest: bool = False
    source: EvidenceSource | None = None

    evidence_quote: str = ""
    explanation: str = ""
    proposed_redline: str = ""
    numeric: NumericEvidence | None = None
    review_reasons: list[str] = field(default_factory=list)
