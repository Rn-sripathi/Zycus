"""The Zycus standard contract playbook, as typed data.

Thresholds live here as data so that changing a rule never means editing logic.
Severities are taken from the playbook's own "why it matters" wording rather than
invented -- see the note on each SERIOUS rule.
"""

from __future__ import annotations

from app.domain.models import Comparison, Rule, RuleType, Severity, Unit

# ---------------------------------------------------------------------------
# Note on the liability cap rule
# ---------------------------------------------------------------------------
# The playbook table words this rule as "must not exceed 12 months of fees",
# but the sample answer key treats a 3-month cap as violating "the 12-month
# minimum". Those are opposite readings of the same sentence.
#
# We implement it as a MINIMUM (cap must be >= 12 months of fees), because
# Zycus is the customer here: the clause caps the *vendor's* liability, so a
# smaller cap means less recourse for Zycus. Reading it as a maximum would make
# the sample's 3-month cap "compliant", which is plainly not the intent.
#
# The ambiguity itself is worth raising with the contract owner.
# ---------------------------------------------------------------------------

PLAYBOOK: tuple[Rule, ...] = (
    Rule(
        id="liability_cap",
        title="Liability cap",
        text="Liability cap must not exceed 12 months of fees paid under the agreement.",
        rationale=(
            "Uncapped or excessive liability exposure is a standard deal-breaker for "
            "procurement contracts."
        ),
        rule_type=RuleType.NUMERIC,
        default_severity=Severity.SERIOUS,  # playbook calls it a "standard deal-breaker"
        threshold=12,
        unit=Unit.MONTHS,
        comparison=Comparison.AT_LEAST,
        anchors=("liability", "shall not exceed", "fees paid", "total liability"),
        keywords=("liability", "limitation of liability", "damages"),
        redline_guidance=(
            "Raise the cap to at least twelve (12) months of fees paid under the "
            "Agreement, and do not accept a blanket exclusion of all consequential "
            "damages in the Vendor's favour only."
        ),
    ),
    Rule(
        id="termination_notice",
        title="Termination for convenience notice",
        text="Termination for convenience requires at least 30 days' written notice.",
        rationale=(
            "Shorter notice periods don't give enough time to transition critical "
            "procurement workflows."
        ),
        rule_type=RuleType.NUMERIC,
        default_severity=Severity.MINOR,  # procedural timing, routinely negotiated up
        threshold=30,
        unit=Unit.DAYS,
        comparison=Comparison.AT_LEAST,
        anchors=(
            "terminate for convenience",
            "termination for convenience",
            "may terminate",
            "for convenience",
        ),
        keywords=("terminate", "termination", "convenience"),
        redline_guidance=(
            "Extend the termination-for-convenience notice period to at least thirty "
            "(30) days' prior written notice."
        ),
    ),
    Rule(
        id="auto_renewal_notice",
        title="Auto-renewal notice",
        text=(
            "Auto-renewal terms must include a notice period of at least 30 days before "
            "renewal, and must be cancellable without penalty."
        ),
        rationale="Silent auto-renewals with penalties trap the company into unwanted terms.",
        rule_type=RuleType.NUMERIC,
        default_severity=Severity.MINOR,  # procedural timing, routinely negotiated up
        threshold=30,
        unit=Unit.DAYS,
        comparison=Comparison.AT_LEAST,
        anchors=(
            "non-renewal",
            "nonrenewal",
            "notice of non-renewal",
            "automatically renewing",
            "renewal",
            "renewing",
        ),
        keywords=("renew", "renewal", "auto-renew", "term"),
        redline_guidance=(
            "Require at least thirty (30) days' notice of non-renewal and state "
            "explicitly that non-renewal carries no penalty or early-termination fee."
        ),
    ),
    Rule(
        id="data_ownership",
        title="Data ownership",
        text=(
            "All data processed under the agreement remains the property of Zycus (or its "
            "customer, where applicable)."
        ),
        rationale="Ambiguous data ownership clauses create downstream compliance and IP risk.",
        rule_type=RuleType.QUALITATIVE,
        default_severity=Severity.SERIOUS,  # playbook cites compliance and IP risk
        keywords=("data", "ownership", "derivative works", "insights"),
        redline_guidance=(
            "Vest ownership of all data, insights and derivative works in Customer, and "
            "limit Vendor to a narrow licence to process that data solely to deliver the "
            "services -- not to improve its products generally."
        ),
    ),
    Rule(
        id="mutual_indemnification",
        title="Mutual indemnification",
        text="Indemnification must be mutual, not one-sided.",
        rationale="One-sided indemnification unfairly shifts risk onto Zycus.",
        rule_type=RuleType.QUALITATIVE,
        default_severity=Severity.SERIOUS,  # playbook: "unfairly shifts risk onto Zycus"
        keywords=("indemnify", "indemnification", "hold harmless", "defend"),
        redline_guidance=(
            "Make the indemnity reciprocal: each party indemnifies the other for claims "
            "arising from its own acts, omissions, or infringement."
        ),
    ),
    Rule(
        id="payment_terms",
        title="Payment terms",
        text="Payment terms should be Net 30 or longer; anything shorter needs escalation.",
        rationale="Shorter payment cycles create working-capital strain and are non-standard.",
        rule_type=RuleType.NUMERIC,
        default_severity=Severity.SERIOUS,  # the rule itself says "needs escalation"
        threshold=30,
        unit=Unit.DAYS,
        comparison=Comparison.AT_LEAST,
        anchors=(
            "shall pay",
            "invoiced amounts",
            "of receipt",
            "payment",
            "invoice",
            "net",
        ),
        keywords=("payment", "fees", "invoice", "pay"),
        redline_guidance=(
            "Move to Net 30 or longer from receipt of a valid invoice, and cap late-payment "
            "interest at a commercially standard rate."
        ),
    ),
    Rule(
        id="governing_law",
        title="Governing law / jurisdiction",
        text=(
            "Governing law/jurisdiction should be a mutually neutral or Zycus-favorable "
            "jurisdiction, not automatically the counterparty's home jurisdiction."
        ),
        rationale="Unfavorable jurisdiction increases legal cost and risk if disputes arise.",
        rule_type=RuleType.QUALITATIVE,
        default_severity=Severity.MINOR,  # negotiable venue question, not a deal-breaker alone
        keywords=("governing law", "jurisdiction", "courts", "venue", "construed"),
        redline_guidance=(
            "Replace the Vendor's home jurisdiction with a mutually neutral forum (for "
            "example Delaware, USA) governing both the agreement and any disputes."
        ),
    ),
)

RULES_BY_ID: dict[str, Rule] = {rule.id: rule for rule in PLAYBOOK}

VALID_RULE_IDS: tuple[str, ...] = tuple(RULES_BY_ID)


def get_rule(rule_id: str) -> Rule | None:
    return RULES_BY_ID.get(rule_id)
