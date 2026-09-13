"""Truth table for the confidence/severity decision logic.

Runs without an API key. This is the logic the demo has to defend, so every branch
is pinned here rather than checked by eye in the UI.
"""

from __future__ import annotations

from app.domain.models import (
    EvidenceSource,
    GateResult,
    LLMAssessment,
    NumericEvidence,
    Severity,
    Tier,
    Unit,
    Verdict,
)
from app.domain.playbook import RULES_BY_ID
from app.pipeline.hitl import classify

TERMINATION = RULES_BY_ID["termination_notice"]  # default severity: minor
PAYMENT = RULES_BY_ID["payment_terms"]  # default severity: serious
DATA = RULES_BY_ID["data_ownership"]  # qualitative, serious

VIOLATION = NumericEvidence(
    result=GateResult.VERIFIED_VIOLATION,
    found_value=7,
    threshold=30,
    unit=Unit.DAYS,
)
COMPLIANT = NumericEvidence(
    result=GateResult.VERIFIED_COMPLIANT,
    found_value=60,
    threshold=30,
    unit=Unit.DAYS,
)
NOT_EXTRACTABLE = NumericEvidence(result=GateResult.NOT_EXTRACTABLE)


class TestArithmeticEvidence:
    def test_verified_violation_is_high_confidence_and_auto_suggested(self):
        decision = classify(TERMINATION, numeric=VIOLATION)
        assert decision.verdict is Verdict.DEVIATION
        assert decision.tier is Tier.HIGH
        assert decision.auto_suggest is True
        assert decision.needs_review is False
        assert decision.source is EvidenceSource.DETERMINISTIC

    def test_verified_compliant_is_not_flagged(self):
        decision = classify(TERMINATION, numeric=COMPLIANT)
        assert decision.verdict is Verdict.COMPLIANT
        assert decision.tier is Tier.HIGH
        assert decision.auto_suggest is False
        assert decision.needs_review is False

    def test_arithmetic_wins_over_model_opinion(self):
        # Model disagrees with the arithmetic; arithmetic is not overridden.
        disagreeing = LLMAssessment(
            violation=False, confidence=0.99, evidence_quote="x", reasoning="y"
        )
        decision = classify(TERMINATION, numeric=VIOLATION, assessment=disagreeing)
        assert decision.verdict is Verdict.DEVIATION
        assert decision.source is EvidenceSource.DETERMINISTIC


class TestModelEvidence:
    def test_confident_violation_with_quote_is_medium_and_auto_suggested(self):
        assessment = LLMAssessment(
            violation=True,
            confidence=0.95,
            evidence_quote="shall be owned by Vendor",
            reasoning="Vendor owns the data.",
        )
        decision = classify(DATA, assessment=assessment)
        assert decision.verdict is Verdict.DEVIATION
        assert decision.tier is Tier.MEDIUM
        assert decision.auto_suggest is True
        assert decision.needs_review is False

    def test_unconfident_violation_is_low_and_flagged_not_auto_suggested(self):
        assessment = LLMAssessment(
            violation=True,
            confidence=0.4,
            evidence_quote="consistent with each party's respective interests",
            reasoning="Ambiguous.",
        )
        decision = classify(DATA, assessment=assessment)
        assert decision.verdict is Verdict.DEVIATION
        assert decision.tier is Tier.LOW
        assert decision.auto_suggest is False
        assert decision.needs_review is True
        assert decision.review_reasons

    def test_violation_without_a_quote_is_downgraded_however_confident(self):
        assessment = LLMAssessment(
            violation=True, confidence=0.99, evidence_quote="", reasoning="Trust me."
        )
        decision = classify(DATA, assessment=assessment)
        assert decision.tier is Tier.LOW
        assert decision.auto_suggest is False
        assert decision.needs_review is True

    def test_unconfident_pass_is_flagged_rather_than_silently_approved(self):
        # The failure mode this system exists to avoid.
        assessment = LLMAssessment(
            violation=False,
            confidence=0.35,
            evidence_quote="",
            reasoning="Hard to tell from the wording.",
        )
        decision = classify(DATA, assessment=assessment)
        assert decision.verdict is Verdict.COMPLIANT
        assert decision.tier is Tier.LOW
        assert decision.needs_review is True
        assert decision.review_reasons

    def test_confident_pass_is_cleared_without_review(self):
        assessment = LLMAssessment(
            violation=False,
            confidence=0.93,
            evidence_quote="each party indemnifies the other",
            reasoning="Mutual.",
        )
        decision = classify(DATA, assessment=assessment)
        assert decision.verdict is Verdict.COMPLIANT
        assert decision.needs_review is False
        assert decision.review_reasons == []


class TestSeverityIsIndependentOfConfidence:
    def test_certain_but_minor(self):
        decision = classify(TERMINATION, numeric=VIOLATION)
        assert decision.tier is Tier.HIGH
        assert decision.severity is Severity.MINOR

    def test_certain_and_serious(self):
        decision = classify(PAYMENT, numeric=VIOLATION)
        assert decision.tier is Tier.HIGH
        assert decision.severity is Severity.SERIOUS

    def test_uncertain_but_serious_still_carries_serious_severity(self):
        assessment = LLMAssessment(
            violation=True, confidence=0.5, evidence_quote="maybe", reasoning="unclear"
        )
        decision = classify(DATA, assessment=assessment)
        assert decision.tier is Tier.LOW
        assert decision.severity is Severity.SERIOUS


class TestNoEvidence:
    def test_missing_evidence_is_never_treated_as_approval(self):
        decision = classify(DATA, numeric=NOT_EXTRACTABLE, assessment=None)
        assert decision.needs_review is True
        assert decision.tier is Tier.LOW
