"""End-to-end check against the real sample contract.

Requires OPENAI_API_KEY and makes real model calls, so it is skipped by default
and the rest of the suite stays fast and offline. Run it with:

    OPENAI_API_KEY=sk-... python -m pytest tests/test_integration_live.py -v -s

This encodes the acceptance criteria for the assignment: every planted deviation
caught, attributed to the right rule, with the right severity and confidence tier.
"""

from __future__ import annotations

import asyncio
import re
from pathlib import Path

import pytest

from app.config import get_settings
from app.domain.models import EvidenceSource, Severity, Tier, Verdict
from app.llm.client import LLMClient
from app.pipeline.orchestrator import review_contract

pytestmark = pytest.mark.skipif(
    not get_settings().llm_enabled,
    reason="OPENAI_API_KEY not configured; live integration test skipped",
)

DATA = Path(__file__).resolve().parents[1] / "app" / "data"
SAMPLE = (DATA / "sample_contract.txt").read_text(encoding="utf-8")
AMBIGUOUS = (DATA / "ambiguous_clause.txt").read_text(encoding="utf-8")

# The seven planted rule violations, and the clause each one lives in.
EXPECTED_VIOLATIONS = {
    ("auto_renewal_notice", 1),
    ("termination_notice", 1),
    ("payment_terms", 2),
    ("liability_cap", 3),
    ("mutual_indemnification", 4),
    ("data_ownership", 5),
    ("governing_law", 6),
}


@pytest.fixture(scope="module")
def review():
    return asyncio.run(review_contract(SAMPLE, LLMClient()))


@pytest.fixture(scope="module")
def ambiguous_review():
    return asyncio.run(review_contract(AMBIGUOUS, LLMClient()))


def _deviations(result):
    return {
        (f.rule_id, f.clause_number)
        for f in result.findings
        if f.verdict is Verdict.DEVIATION
    }


class TestCoverage:
    def test_all_eight_clauses_are_accounted_for(self, review):
        assert review.summary.clauses_reviewed == 8

    def test_every_planted_violation_is_caught(self, review):
        missing = EXPECTED_VIOLATIONS - _deviations(review)
        assert not missing, f"missed deviations: {sorted(missing)}"

    def test_clause_one_yields_two_separate_findings(self, review):
        rules = {f.rule_id for f in review.findings if f.clause_number == 1}
        assert {"termination_notice", "auto_renewal_notice"} <= rules

    def test_boilerplate_clauses_are_not_flagged(self, review):
        flagged = {c for _, c in _deviations(review)}
        assert 7 not in flagged, "confidentiality clause should not be a deviation"
        assert 8 not in flagged, "entire-agreement clause should not be a deviation"


class TestNumericFindingsAreArithmetic:
    @pytest.mark.parametrize(
        ("rule_id", "expected_value"),
        [
            ("termination_notice", 7),
            ("auto_renewal_notice", 10),
            ("payment_terms", 15),
            ("liability_cap", 3),
        ],
    )
    def test_numeric_rules_are_verified_without_the_model(
        self, review, rule_id, expected_value
    ):
        finding = next(f for f in review.findings if f.rule_id == rule_id)
        assert finding.verdict is Verdict.DEVIATION
        assert finding.tier is Tier.HIGH
        assert finding.source is EvidenceSource.DETERMINISTIC
        assert finding.numeric is not None
        assert finding.numeric.found_value == expected_value


class TestSeverityMatchesThePlaybook:
    @pytest.mark.parametrize(
        "rule_id",
        ["payment_terms", "liability_cap", "mutual_indemnification", "data_ownership"],
    )
    def test_escalation_worthy_rules_are_serious(self, review, rule_id):
        finding = next(f for f in review.findings if f.rule_id == rule_id)
        assert finding.severity is Severity.SERIOUS

    @pytest.mark.parametrize("rule_id", ["termination_notice", "auto_renewal_notice"])
    def test_notice_period_gaps_are_negotiable(self, review, rule_id):
        finding = next(f for f in review.findings if f.rule_id == rule_id)
        assert finding.severity is Severity.MINOR


class TestRedlines:
    def test_every_deviation_has_replacement_language(self, review):
        for finding in review.findings:
            if finding.verdict is Verdict.DEVIATION:
                assert finding.proposed_redline, f"{finding.rule_id} produced no redline"

    def test_redlines_are_clause_text_not_commentary(self, review):
        hedges = ("consider revising", "should be negotiated", "this clause is risky")
        for finding in review.findings:
            if finding.proposed_redline:
                lowered = finding.proposed_redline.lower()
                assert not any(h in lowered for h in hedges)

    def test_clause_with_two_breaches_gets_one_replacement_fixing_both(self, review):
        """Regression: per-rule drafting produced texts that each undid the other's fix.

        Clause 1 breaches two rules and each redline replaced the whole clause, so the
        two drafts could not both be applied, and each silently kept the other
        violation in place.
        """
        clause_one = [
            f
            for f in review.findings
            if f.clause_number == 1 and f.verdict is Verdict.DEVIATION
        ]
        assert len(clause_one) == 2

        texts = {f.proposed_redline for f in clause_one}
        assert len(texts) == 1, "clause 1 produced conflicting replacements"

        redline = texts.pop().lower()
        assert not re.search(r"\b7 days|seven \(7\) days", redline), "7-day notice survived"
        assert not re.search(r"\b10 days|ten \(10\) days", redline), "10-day notice survived"
        assert "30" in redline or "thirty" in redline

    def test_numeric_redlines_state_the_required_threshold(self, review):
        for rule_id, threshold in [
            ("termination_notice", "30"),
            ("auto_renewal_notice", "30"),
            ("payment_terms", "30"),
            ("liability_cap", "12"),
        ]:
            finding = next(f for f in review.findings if f.rule_id == rule_id)
            text = finding.proposed_redline.lower()
            assert threshold in text or _spelled(threshold) in text


class TestUncertaintyBranch:
    """The shipped sample is deliberately unambiguous, so the low-confidence path
    is exercised against the vague draft instead."""

    def test_vague_contract_produces_findings_needing_review(self, ambiguous_review):
        flagged = [f for f in ambiguous_review.findings if f.needs_review]
        assert flagged, "no finding was routed to a human on a deliberately vague contract"

    def test_flagged_findings_are_not_auto_suggested(self, ambiguous_review):
        for finding in ambiguous_review.findings:
            if finding.needs_review:
                assert finding.auto_suggest is False
                assert finding.review_reasons


def _spelled(threshold: str) -> str:
    return {"30": "thirty", "12": "twelve"}.get(threshold, threshold)
