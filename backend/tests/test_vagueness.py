"""Tests for deterministic vagueness detection and its effect on routing.

The discrimination that matters: fire on clauses that defer their substance
elsewhere, stay silent on clauses that state a clear (if unfavourable) position.
A false positive here costs a reviewer a glance; a false negative means a clause
nobody read gets approved.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.domain.models import LLMAssessment, Tier, Verdict
from app.domain.playbook import RULES_BY_ID
from app.tools.hitl import classify
from app.tools.segmenter import segment_clauses
from app.tools.vagueness import detect_hedges

DATA = Path(__file__).resolve().parents[1] / "app" / "data"
SAMPLE = (DATA / "sample_contract.txt").read_text(encoding="utf-8")
AMBIGUOUS = (DATA / "ambiguous_clause.txt").read_text(encoding="utf-8")

DATA_RULE = RULES_BY_ID["data_ownership"]


def _clause(text: str, number: int):
    return next(c for c in segment_clauses(text) if c.number == number)


class TestDetection:
    @pytest.mark.parametrize(
        "text",
        [
            "limited to a commercially reasonable amount",
            "upon reasonable prior written notice",
            "such notice period to be determined by the parties",
            "as the parties may mutually determine to be appropriate",
            "consistent with customary industry allocation of risk",
            "in accordance with the parties' customary course of dealing",
            "handled in a manner consistent with each party's respective interests",
        ],
    )
    def test_flags_deferring_language(self, text):
        assert detect_hedges(text)

    @pytest.mark.parametrize(
        "text",
        [
            "Vendor shall have no indemnification obligations to Customer.",
            "All data shall be owned by Vendor.",
            "governed by the laws of the jurisdiction in which Vendor's headquarters is located",
            "Customer shall pay all invoiced amounts within 15 days of receipt.",
        ],
    )
    def test_ignores_clear_positions_however_unfavourable(self, text):
        assert detect_hedges(text) == []

    def test_no_false_positives_on_the_sample_contract_findings(self):
        # Clauses 1-6 carry the planted deviations and must stay confidently actionable.
        for number in range(1, 7):
            clause = _clause(SAMPLE, number)
            assert detect_hedges(clause.full_text) == [], f"clause {number} wrongly hedged"

    def test_fires_on_every_clause_of_the_vague_draft(self):
        for clause in segment_clauses(AMBIGUOUS):
            assert detect_hedges(clause.full_text), f"clause {clause.number} not detected"


class TestRoutingEffect:
    """Vagueness overrides the model's self-reported confidence."""

    CONFIDENT_VIOLATION = LLMAssessment(
        violation=True,
        confidence=0.95,
        evidence_quote="handled in a manner consistent with each party's respective interests",
        reasoning="Vendor may use the data.",
    )

    def test_hedged_clause_is_flagged_despite_high_confidence(self):
        decision = classify(
            DATA_RULE,
            assessment=self.CONFIDENT_VIOLATION,
            hedges=["an appeal to the parties' respective interests"],
        )
        assert decision.tier is Tier.LOW
        assert decision.auto_suggest is False
        assert decision.needs_review is True
        assert any("rather than stating a position" in r for r in decision.review_reasons)

    def test_same_assessment_without_hedges_is_auto_suggested(self):
        decision = classify(DATA_RULE, assessment=self.CONFIDENT_VIOLATION, hedges=[])
        assert decision.tier is Tier.MEDIUM
        assert decision.auto_suggest is True

    def test_confident_pass_on_hedged_clause_is_not_silently_approved(self):
        """The failure this guard exists for: the model rated a clause naming no
        jurisdiction at all as compliant, with 0.9 confidence."""
        assessment = LLMAssessment(
            violation=False,
            confidence=0.9,
            evidence_quote="such jurisdiction as the parties may mutually determine",
            reasoning="Neutral by agreement.",
        )
        decision = classify(
            RULES_BY_ID["governing_law"],
            assessment=assessment,
            hedges=["terms left to later agreement"],
        )
        assert decision.verdict is Verdict.COMPLIANT
        assert decision.needs_review is True
        assert decision.tier is Tier.LOW

    def test_vagueness_never_overrides_arithmetic(self):
        """A number is a number regardless of woolly prose around it."""
        from app.domain.models import GateResult, NumericEvidence, Unit

        decision = classify(
            RULES_BY_ID["termination_notice"],
            numeric=NumericEvidence(
                result=GateResult.VERIFIED_VIOLATION,
                found_value=7,
                threshold=30,
                unit=Unit.DAYS,
            ),
            hedges=["an undefined reasonableness standard"],
        )
        assert decision.tier is Tier.HIGH
        assert decision.auto_suggest is True
        assert decision.needs_review is False
