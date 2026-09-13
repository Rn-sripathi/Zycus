"""Transport-layer DTOs.

Separate from the domain dataclasses so the wire format can change without
touching pipeline logic.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.domain.models import Finding, NumericEvidence, ReviewResult, ReviewSummary, Rule


class ReviewRequest(BaseModel):
    contract_text: str = Field(min_length=1, max_length=120_000)


class NumericEvidenceOut(BaseModel):
    result: str
    found_value: float | None = None
    threshold: float | None = None
    unit: str | None = None
    excerpt: str = ""
    explanation: str = ""

    @classmethod
    def from_domain(cls, evidence: NumericEvidence) -> "NumericEvidenceOut":
        return cls(
            result=evidence.result.value,
            found_value=evidence.found_value,
            threshold=evidence.threshold,
            unit=evidence.unit.value if evidence.unit else None,
            excerpt=evidence.excerpt,
            explanation=evidence.explanation,
        )


class FindingOut(BaseModel):
    clause_number: int
    clause_heading: str
    rule_id: str | None
    rule_title: str | None
    verdict: str
    tier: str | None
    severity: str | None
    auto_suggest: bool
    needs_review: bool
    source: str | None
    original_text: str
    evidence_quote: str
    explanation: str
    proposed_redline: str
    change_summary: str
    redline_addresses: list[str]
    review_reasons: list[str]
    numeric: NumericEvidenceOut | None = None

    @classmethod
    def from_domain(cls, finding: Finding) -> "FindingOut":
        return cls(
            clause_number=finding.clause_number,
            clause_heading=finding.clause_heading,
            rule_id=finding.rule_id,
            rule_title=finding.rule_title,
            verdict=finding.verdict.value,
            tier=finding.tier.value if finding.tier else None,
            severity=finding.severity.value if finding.severity else None,
            auto_suggest=finding.auto_suggest,
            needs_review=finding.needs_review,
            source=finding.source.value if finding.source else None,
            original_text=finding.original_text,
            evidence_quote=finding.evidence_quote,
            explanation=finding.explanation,
            proposed_redline=finding.proposed_redline,
            change_summary=finding.change_summary,
            redline_addresses=finding.redline_addresses,
            review_reasons=finding.review_reasons,
            numeric=(
                NumericEvidenceOut.from_domain(finding.numeric) if finding.numeric else None
            ),
        )


class SummaryOut(BaseModel):
    clauses_reviewed: int
    deviations: int
    serious: int
    minor: int
    auto_suggested: int
    needs_review: int
    clauses_without_applicable_rule: int
    elapsed_seconds: float

    @classmethod
    def from_domain(cls, summary: ReviewSummary) -> "SummaryOut":
        return cls(**summary.__dict__)


class ReviewResponse(BaseModel):
    summary: SummaryOut
    findings: list[FindingOut]

    @classmethod
    def from_domain(cls, result: ReviewResult) -> "ReviewResponse":
        return cls(
            summary=SummaryOut.from_domain(result.summary),
            findings=[FindingOut.from_domain(f) for f in result.findings],
        )


class RuleOut(BaseModel):
    id: str
    title: str
    text: str
    rationale: str
    rule_type: str
    default_severity: str
    threshold: float | None = None
    unit: str | None = None

    @classmethod
    def from_domain(cls, rule: Rule) -> "RuleOut":
        return cls(
            id=rule.id,
            title=rule.title,
            text=rule.text,
            rationale=rule.rationale,
            rule_type=rule.rule_type.value,
            default_severity=rule.default_severity.value,
            threshold=rule.threshold,
            unit=rule.unit.value if rule.unit else None,
        )


class SamplesResponse(BaseModel):
    sample_contract: str
    ambiguous_contract: str


class HealthResponse(BaseModel):
    status: str
    llm_configured: bool
    model: str
