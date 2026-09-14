"""Orchestrator wiring, verified against a stubbed model.

No API key and no network: the fake client returns canned structured responses,
which is enough to prove the six steps hand data to each other correctly, that
arithmetic short-circuits the model, and that redlines land on the right findings.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from app.domain.models import EvidenceSource, Severity, Tier, Verdict
from app.orchestrator import review_contract

SAMPLE = (
    Path(__file__).resolve().parents[1] / "app" / "data" / "sample_contract.txt"
).read_text(encoding="utf-8")

# What the rule matcher would return for the sample contract.
MATCHES = {
    1: ["termination_notice", "auto_renewal_notice"],
    2: ["payment_terms"],
    3: ["liability_cap"],
    4: ["mutual_indemnification"],
    5: ["data_ownership"],
    6: ["governing_law"],
    7: [],
    8: [],
}


class FakeLLMClient:
    """Stands in for LLMClient, recording what it was asked."""

    def __init__(self, *, confidence: float = 0.95, violation: bool = True) -> None:
        self.confidence = confidence
        self.violation = violation
        self.calls: list[str] = []
        # Overridable so a test can drive a different playbook.
        self.matches: dict[int, list[str]] = dict(MATCHES)
        # Records the schema each call was constrained by, which is how the
        # rule-id enum is asserted on.
        self.schemas: dict[str, dict] = {}

    async def complete_json(self, *, schema_name: str, schema: dict | None = None, **kwargs):
        self.calls.append(schema_name)
        if schema is not None:
            self.schemas[schema_name] = schema

        if schema_name == "rule_matches":
            return {
                "matches": [
                    {"clause_number": number, "rule_ids": rule_ids}
                    for number, rule_ids in self.matches.items()
                ]
            }

        if schema_name == "compliance_assessment":
            return {
                "violation": self.violation,
                "confidence": self.confidence,
                "evidence_quote": "shall be owned by Vendor",
                "reasoning": "Stubbed reasoning.",
            }

        if schema_name == "redline_draft":
            return {
                "proposed_redline": "Stubbed replacement clause text.",
                "change_summary": "Stubbed summary.",
            }

        raise AssertionError(f"unexpected schema {schema_name}")


@pytest.fixture
def client():
    return FakeLLMClient()


@pytest.fixture
def result(client):
    return asyncio.run(review_contract(SAMPLE, client))


class TestPipelineWiring:
    def test_reviews_every_clause(self, result):
        assert result.summary.clauses_reviewed == 8

    def test_produces_one_finding_per_matched_rule(self, result):
        pairs = {(f.clause_number, f.rule_id) for f in result.findings if f.rule_id}
        assert pairs == {
            (number, rule_id)
            for number, rule_ids in MATCHES.items()
            for rule_id in rule_ids
        }

    def test_clause_with_no_matching_rule_is_reported_as_uncovered(self, result):
        uncovered = [
            f.clause_number
            for f in result.findings
            if f.verdict is Verdict.NO_APPLICABLE_RULE
        ]
        assert sorted(uncovered) == [7, 8]
        assert result.summary.clauses_without_applicable_rule == 2

    def test_rule_matcher_is_called_once_not_per_clause(self, client, result):
        assert client.calls.count("rule_matches") == 1


class TestArithmeticShortCircuit:
    def test_numeric_rules_never_reach_the_model(self, client, result):
        # Four numeric rules match, all with extractable numbers, so only the three
        # qualitative rules should require a compliance call.
        assert client.calls.count("compliance_assessment") == 3

    def test_numeric_findings_are_marked_deterministic(self, result):
        for rule_id in (
            "termination_notice",
            "auto_renewal_notice",
            "payment_terms",
            "liability_cap",
        ):
            finding = next(f for f in result.findings if f.rule_id == rule_id)
            assert finding.source is EvidenceSource.DETERMINISTIC
            assert finding.tier is Tier.HIGH

    def test_clause_one_numbers_are_attributed_correctly(self, result):
        termination = next(f for f in result.findings if f.rule_id == "termination_notice")
        renewal = next(f for f in result.findings if f.rule_id == "auto_renewal_notice")
        assert termination.numeric.found_value == 7
        assert renewal.numeric.found_value == 10


class TestRedlineRouting:
    def test_every_deviation_receives_its_own_redline(self, result):
        deviations = [f for f in result.findings if f.verdict is Verdict.DEVIATION]
        assert deviations
        assert all(f.proposed_redline for f in deviations)

    def test_non_deviations_get_no_redline(self, result):
        for finding in result.findings:
            if finding.verdict is not Verdict.DEVIATION:
                assert finding.proposed_redline == ""

    def test_one_redline_call_per_clause_not_per_rule(self, client, result):
        # Six clauses deviate; clause 1 breaches two rules but must still be drafted once.
        deviating_clauses = {
            f.clause_number for f in result.findings if f.verdict is Verdict.DEVIATION
        }
        assert client.calls.count("redline_draft") == len(deviating_clauses)
        assert len(deviating_clauses) == 6

    def test_findings_on_the_same_clause_share_one_replacement(self, result):
        """Regression: separately drafted redlines each undid the other's fix.

        Clause 1 breaches the termination-notice and auto-renewal-notice rules. Because
        each redline replaces the whole clause, two independent drafts cannot both be
        applied -- and each silently preserved the other violation.
        """
        clause_one = [
            f
            for f in result.findings
            if f.clause_number == 1 and f.verdict is Verdict.DEVIATION
        ]
        assert len(clause_one) == 2

        texts = {f.proposed_redline for f in clause_one}
        assert len(texts) == 1, "clause 1 produced conflicting replacement texts"

        for finding in clause_one:
            assert len(finding.redline_addresses) == 2

    def test_single_issue_clauses_are_not_labelled_as_combined(self, result):
        single = next(f for f in result.findings if f.rule_id == "payment_terms")
        assert single.redline_addresses == []


class TestSummaryAndOrdering:
    def test_summary_counts_match_the_findings(self, result):
        deviations = [f for f in result.findings if f.verdict is Verdict.DEVIATION]
        assert result.summary.deviations == len(deviations)
        assert result.summary.serious == sum(
            1 for f in deviations if f.severity is Severity.SERIOUS
        )
        assert result.summary.minor == sum(
            1 for f in deviations if f.severity is Severity.MINOR
        )

    def test_deviations_are_listed_before_everything_else(self, result):
        verdicts = [f.verdict for f in result.findings]
        first_non_deviation = next(
            i for i, v in enumerate(verdicts) if v is not Verdict.DEVIATION
        )
        assert all(v is not Verdict.DEVIATION for v in verdicts[first_non_deviation:])


class TestLowConfidenceHandling:
    def test_unconfident_model_findings_are_routed_to_a_human(self):
        client = FakeLLMClient(confidence=0.3)
        result = asyncio.run(review_contract(SAMPLE, client))

        flagged = [f for f in result.findings if f.needs_review]
        assert flagged
        assert all(not f.auto_suggest for f in flagged)
        assert result.summary.needs_review == len(flagged)

    def test_arithmetic_findings_stay_confident_even_when_model_is_unsure(self):
        client = FakeLLMClient(confidence=0.1)
        result = asyncio.run(review_contract(SAMPLE, client))

        numeric = next(f for f in result.findings if f.rule_id == "payment_terms")
        assert numeric.tier is Tier.HIGH
        assert numeric.needs_review is False


class TestEdgeCases:
    def test_empty_contract_returns_no_findings(self, client):
        result = asyncio.run(review_contract("", client))
        assert result.findings == []
        assert result.summary.clauses_reviewed == 0

    def test_text_without_numbered_clauses_returns_no_findings(self, client):
        result = asyncio.run(review_contract("Just a paragraph of prose.", client))
        assert result.findings == []
