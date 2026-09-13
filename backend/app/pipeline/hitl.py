"""Pipeline step 6: decide what a human needs to look at.

This is the product judgment of the system, and it is deliberately a plain
function with no model in it: the model reports evidence, this code decides what
that evidence is worth.

Two axes, kept independent:

  Confidence (how sure are we?)   HIGH   arithmetic, no model judgment involved
                                  MEDIUM model found unambiguous quoted evidence
                                  LOW    model was unsure -> a human decides

  Severity   (how bad is it?)     from the playbook's own rationale, not guessed

They are orthogonal on purpose. A deviation can be certain but minor (Net 15
payment terms), or uncertain but serious if real (a vague data-rights clause).
Collapsing them into one "risk score" would hide exactly the cases a reviewer
most needs to see.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.domain.models import (
    EvidenceSource,
    GateResult,
    LLMAssessment,
    NumericEvidence,
    Rule,
    Severity,
    Tier,
    Verdict,
)


@dataclass(frozen=True)
class Decision:
    verdict: Verdict
    tier: Tier
    source: EvidenceSource
    severity: Severity | None = None
    auto_suggest: bool = False
    needs_review: bool = False
    review_reasons: list[str] = field(default_factory=list)


def classify(
    rule: Rule,
    *,
    numeric: NumericEvidence | None = None,
    assessment: LLMAssessment | None = None,
    confidence_threshold: float = 0.8,
) -> Decision:
    """Turn evidence into a verdict, a confidence tier and a routing decision."""
    if numeric is not None and numeric.result is not GateResult.NOT_EXTRACTABLE:
        return _from_arithmetic(rule, numeric)

    if assessment is not None:
        return _from_model(rule, assessment, confidence_threshold)

    # No evidence of either kind: never treat silence as approval.
    return Decision(
        verdict=Verdict.COMPLIANT,
        tier=Tier.LOW,
        source=EvidenceSource.LLM,
        needs_review=True,
        review_reasons=["No check could be completed for this clause."],
    )


def _from_arithmetic(rule: Rule, numeric: NumericEvidence) -> Decision:
    """Numeric gate settled it. Highest confidence available: it is arithmetic."""
    if numeric.result is GateResult.VERIFIED_VIOLATION:
        return Decision(
            verdict=Verdict.DEVIATION,
            tier=Tier.HIGH,
            source=EvidenceSource.DETERMINISTIC,
            severity=rule.default_severity,
            auto_suggest=True,
        )

    return Decision(
        verdict=Verdict.COMPLIANT,
        tier=Tier.HIGH,
        source=EvidenceSource.DETERMINISTIC,
    )


def _from_model(rule: Rule, assessment: LLMAssessment, threshold: float) -> Decision:
    """No number to check, so the verdict rests on the model's reading."""
    reasons: list[str] = []
    confident = assessment.confidence >= threshold

    # A violation asserted without quoted words cannot be verified by a reviewer at a
    # glance, so it is treated as uncertain however sure the model claims to be.
    unsupported = assessment.violation and not assessment.evidence_quote
    if unsupported:
        reasons.append(
            "The model reported a deviation but did not quote supporting wording from "
            "the clause."
        )

    if not confident:
        reasons.append(
            f"Model confidence {assessment.confidence:.0%} is below the "
            f"{threshold:.0%} auto-suggest threshold."
        )

    trustworthy = confident and not unsupported
    tier = Tier.MEDIUM if trustworthy else Tier.LOW

    if assessment.violation:
        return Decision(
            verdict=Verdict.DEVIATION,
            tier=tier,
            source=EvidenceSource.LLM,
            severity=rule.default_severity,
            auto_suggest=trustworthy,
            needs_review=not trustworthy,
            review_reasons=reasons,
        )

    # "No violation found" with low confidence is not an approval. Silently passing
    # these is the failure mode this system exists to avoid, so it is surfaced too.
    if not trustworthy:
        reasons.append(
            "Reported as compliant, but not confidently enough to clear it without review."
        )

    return Decision(
        verdict=Verdict.COMPLIANT,
        tier=tier,
        source=EvidenceSource.LLM,
        needs_review=not trustworthy,
        review_reasons=reasons if not trustworthy else [],
    )
