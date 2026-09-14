"""Tests for the deterministic numeric gate.

These run without an API key. They pin down the cases most likely to break:
a single clause holding two numbers governed by two different rules, spelled-out
numbers in caps, and never comparing days against months.
"""

from __future__ import annotations

import pytest

from app.domain.models import Clause, GateResult, Unit
from app.domain.playbook import RULES_BY_ID
from app.tools.numeric_gate import evaluate_numeric_rule, extract_quantities

CLAUSE_1 = Clause(
    number=1,
    heading="Term and Termination",
    body=(
        "This Agreement shall commence on the Effective Date and continue for an "
        "initial term of 12 months, automatically renewing for successive 12-month "
        "terms unless either party provides written notice of non-renewal at least "
        "10 days prior to the end of the then-current term. Either party may "
        "terminate for convenience upon 7 days' written notice."
    ),
)

CLAUSE_2 = Clause(
    number=2,
    heading="Fees and Payment",
    body=(
        "Customer shall pay all invoiced amounts within 15 days of receipt. Late "
        "payments shall accrue interest at 2% per month."
    ),
)

CLAUSE_3 = Clause(
    number=3,
    heading="Limitation of Liability",
    body=(
        "VENDOR'S TOTAL LIABILITY UNDER THIS AGREEMENT, WHETHER IN CONTRACT, TORT, "
        "OR OTHERWISE, SHALL NOT EXCEED THE FEES PAID BY CUSTOMER IN THE THREE (3) "
        "MONTHS PRECEDING THE CLAIM."
    ),
)


class TestExtraction:
    def test_finds_both_day_values_in_clause_one(self):
        values = [q.value for q in extract_quantities(CLAUSE_1.body) if q.unit is Unit.DAYS]
        assert values == [10, 7]

    def test_reads_spelled_out_number_in_caps(self):
        months = [q.value for q in extract_quantities(CLAUSE_3.body) if q.unit is Unit.MONTHS]
        assert months == [3]

    def test_ignores_percentage_interest_rate(self):
        # "2% per month" must not be read as a 2-month quantity.
        months = [q.value for q in extract_quantities(CLAUSE_2.body) if q.unit is Unit.MONTHS]
        assert months == []


class TestClauseOneDisambiguation:
    """The crux: one clause, two numbers, two different rules."""

    def test_termination_rule_picks_seven_not_ten(self):
        evidence = evaluate_numeric_rule(CLAUSE_1, RULES_BY_ID["termination_notice"])
        assert evidence.result is GateResult.VERIFIED_VIOLATION
        assert evidence.found_value == 7

    def test_auto_renewal_rule_picks_ten_not_seven(self):
        evidence = evaluate_numeric_rule(CLAUSE_1, RULES_BY_ID["auto_renewal_notice"])
        assert evidence.result is GateResult.VERIFIED_VIOLATION
        assert evidence.found_value == 10

    def test_never_reads_the_twelve_month_term_as_a_notice_period(self):
        for rule_id in ("termination_notice", "auto_renewal_notice"):
            evidence = evaluate_numeric_rule(CLAUSE_1, RULES_BY_ID[rule_id])
            assert evidence.found_value != 12
            assert evidence.unit is Unit.DAYS


class TestThresholdComparison:
    def test_payment_terms_net_15_violates_net_30(self):
        evidence = evaluate_numeric_rule(CLAUSE_2, RULES_BY_ID["payment_terms"])
        assert evidence.result is GateResult.VERIFIED_VIOLATION
        assert evidence.found_value == 15

    def test_three_month_liability_cap_violates_twelve_month_minimum(self):
        evidence = evaluate_numeric_rule(CLAUSE_3, RULES_BY_ID["liability_cap"])
        assert evidence.result is GateResult.VERIFIED_VIOLATION
        assert evidence.found_value == 3
        assert evidence.unit is Unit.MONTHS

    def test_compliant_notice_period_is_verified_not_flagged(self):
        clause = Clause(
            number=1,
            heading="Term and Termination",
            body="Either party may terminate for convenience upon 60 days' written notice.",
        )
        evidence = evaluate_numeric_rule(clause, RULES_BY_ID["termination_notice"])
        assert evidence.result is GateResult.VERIFIED_COMPLIANT
        assert evidence.found_value == 60

    def test_exactly_at_threshold_is_compliant(self):
        clause = Clause(
            number=1,
            heading="Term and Termination",
            body="Either party may terminate for convenience upon 30 days' written notice.",
        )
        evidence = evaluate_numeric_rule(clause, RULES_BY_ID["termination_notice"])
        assert evidence.result is GateResult.VERIFIED_COMPLIANT


class TestFallThroughToLLM:
    def test_vague_clause_with_no_number_is_not_extractable(self):
        clause = Clause(
            number=1,
            heading="Term and Termination",
            body=(
                "Either party may terminate this Agreement for convenience upon "
                "reasonable prior written notice."
            ),
        )
        evidence = evaluate_numeric_rule(clause, RULES_BY_ID["termination_notice"])
        assert evidence.result is GateResult.NOT_EXTRACTABLE

    def test_qualitative_rule_is_rejected(self):
        with pytest.raises(ValueError):
            evaluate_numeric_rule(CLAUSE_1, RULES_BY_ID["data_ownership"])
