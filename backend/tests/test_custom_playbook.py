"""Loading a playbook supplied as JSON.

The point of structured rules rather than free text is that a rule carrying a
threshold, a unit and anchor phrases can still be settled by arithmetic. These
tests hold that line: a custom numeric rule must reach the verified tier exactly
like a shipped one, and a rule that cannot support arithmetic must be rejected
loudly rather than quietly demoted to model judgment.
"""

from __future__ import annotations

import asyncio

import pytest

from app.domain.models import EvidenceSource, RuleType, Severity, Tier, Unit, Verdict
from app.domain.playbook import PLAYBOOK, PlaybookError, rules_from_json, rules_to_json
from app.orchestrator import review_contract
from app.tools.numeric_gate import evaluate_numeric_rule
from app.tools.segmenter import segment_clauses
from tests.test_orchestrator import FakeLLMClient

NUMERIC_RULE = {
    "id": "warranty_period",
    "title": "Warranty period",
    "text": "Vendor must warrant the services for at least 6 months.",
    "rationale": "A short warranty shifts defect risk onto the customer.",
    "rule_type": "numeric",
    "default_severity": "serious",
    "threshold": 6,
    "unit": "months",
    "comparison": "at_least",
    "anchors": ["warrant", "warranty"],
    "keywords": ["warranty", "warrant"],
}

QUALITATIVE_RULE = {
    "id": "subcontracting",
    "title": "Subcontracting",
    "text": "Vendor may not subcontract without prior written consent.",
    "rationale": "Unvetted subcontractors inherit access to customer data.",
    "rule_type": "qualitative",
    "default_severity": "minor",
}


class TestParsing:
    def test_accepts_a_bare_list(self):
        rules = rules_from_json([NUMERIC_RULE, QUALITATIVE_RULE])
        assert [r.id for r in rules] == ["warranty_period", "subcontracting"]

    def test_accepts_a_wrapped_object(self):
        rules = rules_from_json({"rules": [QUALITATIVE_RULE]})
        assert len(rules) == 1

    def test_numeric_fields_survive(self):
        rule = rules_from_json([NUMERIC_RULE])[0]
        assert rule.rule_type is RuleType.NUMERIC
        assert rule.threshold == 6
        assert rule.unit is Unit.MONTHS
        assert rule.anchors == ("warrant", "warranty")
        assert rule.default_severity is Severity.SERIOUS

    def test_the_shipped_playbook_round_trips(self):
        """Export then re-import must produce the same rules, since the export is
        what a user starts editing from."""
        reloaded = rules_from_json(rules_to_json())
        assert len(reloaded) == len(PLAYBOOK)

        for before, after in zip(PLAYBOOK, reloaded, strict=True):
            assert after.id == before.id
            assert after.rule_type is before.rule_type
            assert after.default_severity is before.default_severity
            assert after.threshold == before.threshold
            assert after.unit is before.unit
            assert after.comparison is before.comparison
            assert after.anchors == before.anchors


class TestRejections:
    @pytest.mark.parametrize(
        ("payload", "fragment"),
        [
            ([], "at least one rule"),
            ("not a list", "list of rules"),
            ([{"id": "x"}], "missing"),
            ([{**QUALITATIVE_RULE, "id": "Has Spaces"}], "lowercase"),
            ([{**QUALITATIVE_RULE, "rule_type": "vibes"}], "rule_type"),
            ([{**QUALITATIVE_RULE, "default_severity": "catastrophic"}], "default_severity"),
            ([{**NUMERIC_RULE, "threshold": "soon"}], "numeric threshold"),
            ([{**NUMERIC_RULE, "threshold": -3}], "must be positive"),
            ([{**NUMERIC_RULE, "unit": "fortnights"}], "unit"),
        ],
    )
    def test_bad_input_explains_itself(self, payload, fragment):
        with pytest.raises(PlaybookError, match=fragment):
            rules_from_json(payload)

    def test_duplicate_ids_are_rejected(self):
        with pytest.raises(PlaybookError, match="share the id"):
            rules_from_json([NUMERIC_RULE, dict(NUMERIC_RULE)])

    def test_numeric_rule_without_anchors_is_refused(self):
        """Silently accepting it would demote the rule to model judgment, which is
        exactly the quiet behaviour this design avoids."""
        without = {k: v for k, v in NUMERIC_RULE.items() if k != "anchors"}
        with pytest.raises(PlaybookError, match="no anchors"):
            rules_from_json([without])


class TestArithmeticStillApplies:
    def test_a_custom_numeric_rule_is_checked_by_maths(self):
        rule = rules_from_json([NUMERIC_RULE])[0]
        clause = segment_clauses(
            "1. Warranty. Vendor shall warrant the services for 3 months after delivery."
        )[0]

        evidence = evaluate_numeric_rule(clause, rule)
        assert evidence.found_value == 3
        assert evidence.threshold == 6
        assert "fails the rule" in evidence.explanation

    def test_a_compliant_custom_rule_passes(self):
        rule = rules_from_json([NUMERIC_RULE])[0]
        clause = segment_clauses(
            "1. Warranty. Vendor shall warrant the services for 12 months after delivery."
        )[0]
        assert evaluate_numeric_rule(clause, rule).found_value == 12


class TestEndToEnd:
    CONTRACT = (
        "1. Warranty. Vendor shall warrant the services for 3 months after delivery.\n\n"
        "2. Subcontracting. Vendor may subcontract freely at its own discretion.\n\n"
        "3. General. This is the entire agreement."
    )

    def test_review_runs_against_a_custom_playbook(self):
        rules = rules_from_json([NUMERIC_RULE, QUALITATIVE_RULE])
        client = FakeLLMClient()
        client.matches = {1: ["warranty_period"], 2: ["subcontracting"], 3: []}

        result = asyncio.run(review_contract(self.CONTRACT, client, rules))

        found = {(f.rule_id, f.clause_number) for f in result.findings if f.rule_id}
        assert found == {("warranty_period", 1), ("subcontracting", 2)}

    def test_custom_numeric_finding_reaches_the_verified_tier(self):
        rules = rules_from_json([NUMERIC_RULE, QUALITATIVE_RULE])
        client = FakeLLMClient()
        client.matches = {1: ["warranty_period"], 2: ["subcontracting"], 3: []}

        result = asyncio.run(review_contract(self.CONTRACT, client, rules))
        warranty = next(f for f in result.findings if f.rule_id == "warranty_period")

        assert warranty.verdict is Verdict.DEVIATION
        assert warranty.tier is Tier.HIGH
        assert warranty.source is EvidenceSource.DETERMINISTIC
        assert warranty.severity is Severity.SERIOUS

    def test_clauses_outside_the_custom_playbook_are_reported_uncovered(self):
        rules = rules_from_json([NUMERIC_RULE, QUALITATIVE_RULE])
        client = FakeLLMClient()
        client.matches = {1: ["warranty_period"], 2: ["subcontracting"], 3: []}

        result = asyncio.run(review_contract(self.CONTRACT, client, rules))
        uncovered = [f.clause_number for f in result.findings if f.verdict is Verdict.NO_APPLICABLE_RULE]
        assert uncovered == [3]

    def test_the_model_is_only_offered_the_custom_rule_ids(self):
        """A stale enum would let the model return ids the playbook no longer has."""
        rules = rules_from_json([NUMERIC_RULE, QUALITATIVE_RULE])
        client = FakeLLMClient()
        client.matches = {1: ["warranty_period"], 2: ["subcontracting"], 3: []}

        asyncio.run(review_contract(self.CONTRACT, client, rules))

        schema = client.schemas["rule_matches"]
        offered = schema["properties"]["matches"]["items"]["properties"]["rule_ids"]["items"]["enum"]
        assert set(offered) == {"warranty_period", "subcontracting"}
